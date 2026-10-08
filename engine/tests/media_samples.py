"""Synthetic test media generated with ffmpeg (no binary fixtures in the repo).

sample_video(): 90 s, 1280x720, three colour scenes (cuts at 30 s and 60 s),
quiet tone with a loud burst between 45 s and 55 s.
"""

from __future__ import annotations

import functools
import tempfile
from pathlib import Path

from clipfarm_engine.media import ffmpeg

TMP = Path(tempfile.mkdtemp(prefix="clipfarm-tests-"))


@functools.lru_cache(maxsize=None)
def sample_video() -> Path:
    out = TMP / "sample.mp4"
    graph = (
        "color=c=red:s=1280x720:r=30:d=30[a];color=c=blue:s=1280x720:r=30:d=30[b];"
        "color=c=green:s=1280x720:r=30:d=30[c];[a][b][c]concat=n=3:v=1:a=0[v]"
    )
    audio = "aevalsrc='0.03*sin(2*PI*440*t)+if(between(t,45,55),0.8*sin(2*PI*660*t),0)':s=44100:d=90"
    ffmpeg.run(["-filter_complex", graph, "-f", "lavfi", "-i", audio, "-map", "[v]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out)])
    return out


@functools.lru_cache(maxsize=None)
def short_clip() -> Path:
    out = TMP / "short.mp4"
    ffmpeg.cut(sample_video(), out, 44, 50)
    return out
