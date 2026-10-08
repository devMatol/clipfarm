"""End-to-end pipeline. Every step caches its output in the project folder, so a
re-run only redoes what changed (e.g. re-render with another layout in seconds).

data/projects/<id>/
  source.mp4 | source.json (path of a local file, not copied)
  audio.wav, voice/            speech input (voice isolated with Demucs if enabled)
  words.json                   word-level transcript
  signals.json                 loudness per second + scene cuts
  highlights.json              ranked clip candidates
  clips/NN.raw.mp4, NN.ass, NN.mp4
  manifest.json                what the UI/API reads
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .captions.ass import PRESETS, Word, build_ass
from .config import Settings
from .highlights import llm, select as sel, signals as sig_mod
from .media import ffmpeg, layouts, render

Progress = Callable[[str, float, str], None]


def _log(step: str, pct: float, msg: str) -> None:
    print(f"[{step:<10}] {pct:5.0%} {msg}", flush=True)


@dataclass
class RenderOptions:
    layout: str = "auto"              # auto | center | blur | facecam_top | facecam_bottom
    fmt: str = "9:16"
    cam: layouts.Rect | None = None
    captions: str | None = "punchy"   # preset name, None = no captions
    focus_x: float = 0.5
    skip_if_subtitles_present: bool = True  # Ne pas sous-titrer si du texte est déjà incrusté en bas


@dataclass
class Project:
    id: str
    dir: Path
    source: Path
    clips: list[dict] = field(default_factory=list)


def project_id(source: str) -> str:
    return hashlib.sha1(source.encode()).hexdigest()[:10]


def ingest(source: str, s: Settings, progress: Progress = _log) -> Project:
    pid = project_id(source)
    pdir = s.project_dir(pid)
    if re.match(r"https?://", source):
        target = pdir / "source.mp4"
        meta_file = pdir / "metadata.json"
        if not target.exists():
            progress("ingest", 0.0, f"telechargement {source}")
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
                "--retries", "10",
                "--fragment-retries", "10",
                "--continue",
                "--merge-output-format", "mp4",
                "--write-info-json",
                "-o", str(target),
                source,
            ]
            max_attempts = 2
            last_err = ""
            for attempt in range(1, max_attempts + 1):
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    break
                err_text = res.stderr or res.stdout or ""
                lines = [line.strip() for line in err_text.splitlines() if line.strip()]
                last_err = "\n".join(lines[-10:]) if lines else f"yt-dlp a échoué avec le code {res.returncode}"
                if attempt < max_attempts:
                    progress("ingest", 0.0, f"echec yt-dlp (tentative {attempt}/{max_attempts}), nouvel essai...")
            else:
                raise RuntimeError(last_err)

            info_json = pdir / "source.info.json"
            if info_json.exists():
                try:
                    data = json.loads(info_json.read_text(encoding="utf-8"))
                    meta_file.write_text(json.dumps({
                        "title": data.get("title", ""),
                        "description": data.get("description", ""),
                        "uploader": data.get("uploader", ""),
                    }, ensure_ascii=False, indent=1), encoding="utf-8")
                except Exception:
                    pass
        return Project(pid, pdir, target)
    path = Path(source).resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    (pdir / "source.json").write_text(json.dumps({"path": str(path)}), encoding="utf-8")
    meta_file = pdir / "metadata.json"
    if not meta_file.exists():
        meta_file.write_text(json.dumps({"title": path.stem, "description": ""}, ensure_ascii=False, indent=1), encoding="utf-8")
    return Project(pid, pdir, path)


def analyse(p: Project, s: Settings, transcribe: bool = True, progress: Progress = _log) -> tuple[list[Word], sig_mod.Signals]:
    info = ffmpeg.probe(p.source)
    words: list[Word] = []
    words_path = p.dir / "words.json"
    if transcribe and info.has_audio:
        if words_path.exists():
            from .transcribe.speech import load_words
            words = load_words(words_path)
        else:
            from .transcribe import speech
            progress("audio", 0.1, "extraction audio")
            wav = ffmpeg.extract_audio(p.source, p.dir / "audio.wav")
            if s.isolate_voice:
                try:
                    progress("voice", 0.15, "isolation de la voix (Demucs)")
                    wav = speech.isolate_voice(wav, p.dir / "voice")
                except Exception as exc:
                    progress("voice", 0.15, f"isolation ignoree: {exc}")
            progress("transcribe", 0.2, f"transcription {s.whisper_model} sur {s.whisper_device}")
            words = speech.transcribe(wav, s)
            speech.save_words(words, words_path)
    sig_path = p.dir / "signals.json"
    if sig_path.exists():
        signals = sig_mod.Signals(**json.loads(sig_path.read_text(encoding="utf-8")))
    else:
        progress("signals", 0.5, "volume et changements de plan")
        signals = sig_mod.compute(p.source)
        sig_path.write_text(json.dumps(signals.__dict__), encoding="utf-8")
    return words, signals


def detect(p: Project, words: list[Word], signals: sig_mod.Signals, s: Settings, progress: Progress = _log) -> list[llm.Candidate]:
    progress("highlights", 0.6, f"detection des moments ({s.llm_provider})")
    title, desc = p.source.stem, ""
    meta_path = p.dir / "metadata.json"
    if meta_path.exists():
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            title = m.get("title") or title
            desc = m.get("description") or desc
        except Exception:
            pass
    cands = sel.select(llm.find_candidates(words, signals.duration, s, sig=signals, title=title, description=desc), words, signals, s)
    (p.dir / "highlights.json").write_text(json.dumps([c.to_dict() for c in cands], ensure_ascii=False, indent=1), encoding="utf-8")
    return cands


def render_all(p: Project, cands: list[llm.Candidate], words: list[Word], opts: RenderOptions, progress: Progress = _log) -> list[dict]:
    from .media.face_detect import check_face_in_region
    from .vision import facecam as fc_mod

    # Détection automatique de la facecam si cam.json n'existe pas encore
    cam_json_path = p.dir / "cam.json"
    cam_data: dict = {}
    if cam_json_path.exists():
        try:
            cam_data = json.loads(cam_json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    else:
        try:
            progress("facecam", 0.65, "detection automatique facecam et timeline")
            cam_data = fc_mod.analyze_facecam(p.source, p.dir)
        except Exception as exc:
            progress("facecam", 0.65, f"detection facecam ignoree: {exc}")

    # Priorité absolue au rectangle manuel s'il a été fourni
    active_cam = opts.cam
    if active_cam is None and cam_data.get("cam"):
        try:
            cx, cy, cw, ch = cam_data["cam"]
            active_cam = layouts.Rect(cx, cy, cw, ch)
        except Exception:
            pass

    timeline = cam_data.get("timeline")

    cdir = p.dir / "clips"
    cdir.mkdir(exist_ok=True)
    out = []
    for i, c in enumerate(cands, 1):
        progress("render", 0.7 + 0.3 * (i - 1) / max(1, len(cands)), f"clip {i}/{len(cands)} {c.start:.1f}-{c.end:.1f}")
        raw = ffmpeg.cut(p.source, cdir / f"{i:02d}.raw.mp4", c.start, c.end)

        clip_layout = opts.layout
        if clip_layout == "auto":
            clip_layout = "facecam_top" if active_cam else "center"

        face_fallback = False
        # Si layout facecam sélectionné, vérifier la présence d'un visage sur 3 frames
        if clip_layout in ("facecam_top", "facecam_bottom") and active_cam:
            has_face = check_face_in_region(raw, active_cam, num_samples=3)
            if not has_face:
                clip_layout = "center"
                face_fallback = True

        # Détection OCR des sous-titres déjà incrustés sur le tiers inférieur (RapidOCR)
        has_burned_subs = False
        try:
            from .vision.subtitles_ocr import detect_burned_in_subtitles
            has_burned_subs, detected_count = detect_burned_in_subtitles(
                raw, 0.0, max(0.1, c.end - c.start), sample_count=10, threshold=6
            )
            if has_burned_subs:
                progress("render", 0.7 + 0.3 * (i - 1) / max(1, len(cands)), f"sous-titres incrustés détectés ({detected_count}/10 images)")
        except Exception:
            has_burned_subs = False

        ass_path = None
        if opts.captions and words:
            if has_burned_subs and opts.skip_if_subtitles_present:
                ass_path = None  # L'utilisateur a demandé de ne pas sous-titrer si déjà présents
            else:
                inside = [w for w in words if w.start >= c.start and w.end <= c.end]
                ass_path = cdir / f"{i:02d}.ass"
                # Si des sous-titres sont présents mais l'utilisateur a décoché l'option, placer nos sous-titres en haut
                caption_position = "top" if has_burned_subs else "bottom"
                ass_content = build_ass(
                    inside,
                    PRESETS[opts.captions],
                    play_res=layouts.FORMATS[opts.fmt],
                    offset=c.start,
                    position=caption_position,
                )
                ass_path.write_text(ass_content, encoding="utf-8")

        final = render.render_timeline_clip(
            raw,
            cdir / f"{i:02d}.mp4",
            c.start,
            c.end,
            timeline=timeline,
            cam=active_cam if not face_fallback else None,
            default_layout=clip_layout,
            fmt=opts.fmt,
            ass=ass_path,
            focus_x=opts.focus_x,
        )

        clip_data = {
            **c.to_dict(),
            "file": str(final),
            "index": i,
            "layout": clip_layout if not face_fallback else "center",
            "face_fallback": face_fallback,
            "burned_subtitles_detected": has_burned_subs,
        }
        out.append(clip_data)
    p.clips = out
    (p.dir / "manifest.json").write_text(json.dumps({"id": p.id, "source": str(p.source), "clips": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    progress("done", 1.0, f"{len(out)} clips dans {cdir}")
    return out


def run(source: str, s: Settings | None = None, opts: RenderOptions | None = None, transcribe: bool = True, progress: Progress = _log) -> Project:
    s = s or Settings()
    opts = opts or RenderOptions()
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg introuvable")
    p = ingest(source, s, progress)
    words, signals = analyse(p, s, transcribe, progress)
    cands = detect(p, words, signals, s, progress)
    render_all(p, cands, words, opts, progress)
    return p
