import json

from clipfarm_engine import pipeline
from clipfarm_engine.config import Settings
from clipfarm_engine.media import ffmpeg

from media_samples import TMP, sample_video


def test_end_to_end_without_ai():
    """Signals only (no Whisper, no LLM): must still produce valid vertical clips."""
    s = Settings()
    s.data_dir = TMP / "data"
    s.llm_provider = "none"
    s.max_clips = 2
    s.min_clip_s = 10
    s.max_clip_s = 20
    p = pipeline.run(str(sample_video()), s, pipeline.RenderOptions(layout="blur"), transcribe=False,
                     progress=lambda *a: None)
    manifest = json.loads((p.dir / "manifest.json").read_text(encoding="utf-8"))
    assert 1 <= len(manifest["clips"]) <= 2
    for c in manifest["clips"]:
        info = ffmpeg.probe(c["file"])
        assert (info.width, info.height) == (1080, 1920)
        assert 9 <= info.duration <= 21
    # cache: second run reuses signals.json
    assert (p.dir / "signals.json").exists()
