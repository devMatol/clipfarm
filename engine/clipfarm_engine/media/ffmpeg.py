"""Thin, dependency-free wrappers around the ffmpeg / ffprobe binaries."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def _bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise FFmpegError(f"{name} introuvable dans le PATH")
    return path


_NVENC_AVAILABLE: bool | None = None


def has_nvenc() -> bool:
    """Vérifie si l'encodeur matériel NVIDIA NVENC (h264_nvenc) est disponible."""
    global _NVENC_AVAILABLE
    if _NVENC_AVAILABLE is None:
        try:
            cmd = [_bin("ffmpeg"), "-hide_banner", "-encoders"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
            _NVENC_AVAILABLE = "h264_nvenc" in res.stdout
        except Exception:
            _NVENC_AVAILABLE = False
    return _NVENC_AVAILABLE


def run(args: list[str], cwd: str | Path | None = None, timeout: int = 300) -> str:
    """Run ffmpeg with args, return stderr (ffmpeg logs there). Raises on failure."""
    cmd = [_bin("ffmpeg"), "-hide_banner", "-nostdin", "-y", *args]
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FFmpegError(f"ffmpeg a dépassé le délai imparti ({timeout}s) et a été interrompu.")
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise FFmpegError(f"ffmpeg a echoue ({proc.returncode}):\n{tail}")
    return proc.stderr


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


def probe(path: str | Path) -> MediaInfo:
    cmd = [_bin("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe a echoue sur {path}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    # Some files carry a cover image as a "video" stream: pick the real one.
    videos = [s for s in data["streams"] if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic", 0) == 0]
    if not videos:
        raise FFmpegError(f"aucune piste video dans {path}")
    v = videos[0]
    num, _, den = v.get("avg_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    return MediaInfo(
        duration=float(data["format"].get("duration", 0.0)),
        width=int(v["width"]),
        height=int(v["height"]),
        fps=fps,
        has_audio=any(s.get("codec_type") == "audio" for s in data["streams"]),
    )


def cut(src: str | Path, dst: str | Path, start: float, end: float, crf: int = 14) -> Path:
    """Frame-accurate cut, re-encoded at high quality (input for the final render)."""
    run([
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
        "-c:v", "libx264", "-preset", "fast", "-crf", str(crf),
        "-c:a", "aac", "-b:a", "192k", str(dst),
    ])
    return Path(dst)


def extract_audio(src: str | Path, dst: str | Path, sample_rate: int = 16000) -> Path:
    """Mono WAV for speech models."""
    run(["-i", str(src), "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(dst)])
    return Path(dst)


def frame_at(src: str | Path, t: float, dst: str | Path, width: int | None = None) -> Path:
    vf = ["-vf", f"scale={width}:-2"] if width else []
    run(["-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", *vf, str(dst)])
    return Path(dst)
