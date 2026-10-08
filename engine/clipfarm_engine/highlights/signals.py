"""Cheap, model-free signals computed with ffmpeg: loudness per second and scene cuts.

They work without any AI and are used (1) as a fallback ranking when no LLM is
available and (2) as a bonus on top of the LLM score.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..media import ffmpeg

_RMS = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[\d.]+|-inf|inf|nan)")
_PTS = re.compile(r"pts_time:([\d.]+)")


def loudness_per_second(path: str | Path) -> list[float]:
    """RMS level (dBFS) of each second of audio. Silence is clamped to -90."""
    log = ffmpeg.run([
        "-i", str(path), "-vn", "-af",
        "aresample=16000,asetnsamples=n=16000:p=0,astats=metadata=1:reset=1,ametadata=mode=print:key=lavfi.astats.Overall.RMS_level",
        "-f", "null", "-",
    ])
    out = []
    for m in _RMS.finditer(log):
        v = m.group(1)
        out.append(-90.0 if v in ("-inf", "nan") else max(float(v), -90.0))
    return out


def scene_changes(path: str | Path, threshold: float = 0.3) -> list[float]:
    log = ffmpeg.run([
        "-i", str(path), "-an", "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-",
    ])
    return [float(m.group(1)) for m in _PTS.finditer(log)]


@dataclass
class Signals:
    duration: float
    loudness: list[float] = field(default_factory=list)
    scenes: list[float] = field(default_factory=list)

    def window_score(self, start: float, end: float) -> float:
        """0..1 score: louder than the video average + more cuts = higher."""
        a, b = int(start), max(int(start) + 1, int(end))
        seg = self.loudness[a:b]
        if not seg or not self.loudness:
            return 0.0
        mean = sum(self.loudness) / len(self.loudness)
        var = sum((x - mean) ** 2 for x in self.loudness) / len(self.loudness)
        std = math.sqrt(var) or 1.0
        z = (sum(seg) / len(seg) - mean) / std
        peaks = sum(1 for x in seg if x > mean + 1.5 * std) / len(seg)
        cuts = sum(1 for t in self.scenes if start <= t < end) / max(end - start, 1) * 10  # cuts per 10 s
        raw = 0.5 * z + 1.5 * peaks + 0.3 * min(cuts, 3)
        return 1 / (1 + math.exp(-raw))

    def detect_tags(self, start: float, end: float, prev_end: float | None = None) -> list[str]:
        """Detect context tags for a spoken line: [SILENCE >3s], [CRI], [RIRE], [ACTION]."""
        tags = []

        # 1. Silence avant la réplique
        if prev_end is None:
            if start >= 3.0:
                tags.append("[SILENCE >3s]")
        elif start - prev_end >= 3.0:
            tags.append("[SILENCE >3s]")

        # 2. Analyse sonore (CRI & RIRE)
        if self.loudness:
            mean = sum(self.loudness) / len(self.loudness)
            var = sum((x - mean) ** 2 for x in self.loudness) / len(self.loudness)
            std = math.sqrt(var) or 1.0

            a = max(0, int(start))
            b = min(len(self.loudness), max(a + 1, int(math.ceil(end))))
            seg = self.loudness[a:b]

            if seg:
                # [CRI] si le volume dépasse la moyenne + 1.5 écart-type
                if any(x > mean + 1.5 * std for x in seg):
                    tags.append("[CRI]")

                # [RIRE] détection de pics courts répétés (oscillations rapides d'énergie)
                if len(seg) >= 2:
                    high_points = [x for x in seg if x > mean + 0.3 * std]
                    fluctuations = sum(abs(seg[i] - seg[i - 1]) for i in range(1, len(seg)))
                    if len(high_points) >= 2 and fluctuations >= 6.0:
                        tags.append("[RIRE]")

        # 3. Rythme visuel [ACTION] : au moins 2 cuts ou fréquence >= 0.5 cut/s
        cuts = sum(1 for t in self.scenes if (start - 0.2) <= t <= (end + 0.2))
        duration = max(end - start, 1.0)
        if cuts >= 2 or (cuts >= 1 and duration <= 2.0 and cuts / duration >= 0.5):
            tags.append("[ACTION]")

        return tags



def compute(path: str | Path) -> Signals:
    info = ffmpeg.probe(path)
    return Signals(
        duration=info.duration,
        loudness=loudness_per_second(path) if info.has_audio else [],
        scenes=scene_changes(path),
    )


def candidate_windows(sig: Signals, length: float = 40.0, step: float = 5.0, top: int = 8, min_gap: float = 60.0) -> list[tuple[float, float, float]]:
    """Best non-overlapping windows by signal score: (start, end, score)."""
    scored = []
    t = 0.0
    while t + length <= sig.duration:
        scored.append((t, t + length, sig.window_score(t, t + length)))
        t += step
    scored.sort(key=lambda x: x[2], reverse=True)
    chosen: list[tuple[float, float, float]] = []
    for c in scored:
        if all(abs(c[0] - o[0]) >= min_gap for o in chosen):
            chosen.append(c)
        if len(chosen) >= top:
            break
    return sorted(chosen)
