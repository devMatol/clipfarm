"""CLI: python -m clipfarm_engine run <fichier|url> [options]"""

from __future__ import annotations

import argparse

from . import pipeline
from .config import Settings
from .media.layouts import FORMATS, Rect


def _rect(v: str) -> Rect:
    x, y, w, h = (float(t) for t in v.split(","))
    return Rect(x, y, w, h)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="clipfarm_engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="video longue -> clips")
    r.add_argument("source", help="chemin d'un fichier video ou lien")
    r.add_argument("--layout", default="auto", choices=["auto", "center", "blur", "facecam_top", "facecam_bottom"])
    r.add_argument("--format", default="9:16", choices=list(FORMATS))
    r.add_argument("--cam", type=_rect, help="zone facecam relative x,y,w,h ex: 0.739,0.083,0.246,0.245")
    r.add_argument("--captions", default="punchy", help="preset de sous-titres ou 'none'")
    r.add_argument("--llm", choices=["ollama", "gemini", "none"], help="force le fournisseur LLM")
    r.add_argument("--max-clips", type=int)
    r.add_argument("--min-clip-s", type=float, default=30.0)
    r.add_argument("--max-clip-s", type=float, default=70.0)
    r.add_argument("--skip-if-subtitles-present", action="store_true", default=True)
    r.add_argument("--no-transcribe", action="store_true", help="signaux seulement, sans sous-titres")
    a = ap.parse_args(argv)

    s = Settings()
    if a.llm:
        s.llm_provider = a.llm
    if a.max_clips:
        s.max_clips = a.max_clips
    s.min_clip_s = a.min_clip_s
    s.max_clip_s = a.max_clip_s
    opts = pipeline.RenderOptions(
        layout=a.layout,
        fmt=a.format,
        cam=a.cam,
        captions=None if a.captions == "none" else a.captions,
        skip_if_subtitles_present=a.skip_if_subtitles_present,
    )
    p = pipeline.run(a.source, s, opts, transcribe=not a.no_transcribe)
    for c in p.clips:
        print(f"{c['index']:02d}  {c['start']:7.1f}-{c['end']:7.1f}  score {c['final_score']:.2f}  {c['title'] or c['reason']}")


if __name__ == "__main__":
    main()
