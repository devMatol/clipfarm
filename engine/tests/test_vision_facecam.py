import json
from pathlib import Path

from clipfarm_engine.eval import iou
from clipfarm_engine.media import ffmpeg, layouts
from clipfarm_engine.media.render import render_timeline_clip
from clipfarm_engine.vision.facecam import (
    FaceBox,
    analyze_facecam,
    classify_frame,
    fallback_box,
    smooth_timeline,
)

from media_samples import TMP, short_clip


def test_classify_frame_overlay():
    """Small face in top-right corner must be classified as overlay."""
    face = FaceBox(x=0.75, y=0.10, w=0.10, h=0.12, confidence=0.95)
    frame_type, primary = classify_frame([face])
    assert frame_type == "overlay"
    assert primary == face


def test_classify_frame_fullscreen():
    """Large centered face must be classified as fullscreen."""
    face = FaceBox(x=0.35, y=0.20, w=0.30, h=0.40, confidence=0.95)
    frame_type, primary = classify_frame([face])
    assert frame_type == "fullscreen"
    assert primary == face


def test_classify_frame_gameplay():
    """No face detected must be classified as gameplay."""
    frame_type, primary = classify_frame([])
    assert frame_type == "gameplay"
    assert primary is None


def test_smooth_timeline():
    """Flickers under 3 seconds must be absorbed into surrounding segments."""
    raw_timeline = [
        {"start": 0.0, "end": 10.0, "type": "overlay"},
        {"start": 10.0, "end": 11.5, "type": "gameplay"},  # flicker de 1.5s
        {"start": 11.5, "end": 25.0, "type": "overlay"},
    ]
    smoothed = smooth_timeline(raw_timeline, min_duration=3.0)
    assert len(smoothed) == 1
    assert smoothed[0]["type"] == "overlay"
    assert smoothed[0]["start"] == 0.0
    assert smoothed[0]["end"] == 25.0


def test_fallback_box_aspect_and_headroom():
    """Fallback box must encompass face and remain bounded within 0..1."""
    face = FaceBox(x=0.75, y=0.10, w=0.08, h=0.10, confidence=0.9)
    box = fallback_box(face, aspect=1.0)
    x, y, w, h = box
    assert 0.0 <= x <= 1.0
    assert 0.0 <= y <= 1.0
    assert 0.15 <= w <= 0.40
    assert 0.15 <= h <= 0.40
    # Le visage doit être à l'intérieur
    assert x <= face.x and y <= face.y


def test_golden_facecam_iou_above_threshold():
    """analyze_facecam on golden sample must achieve IoU >= 0.8 with reference cam box."""
    golden_path = Path(__file__).parent / "golden" / "gta6_sample.json"
    assert golden_path.exists()
    golden_data = json.loads(golden_path.read_text(encoding="utf-8"))
    truth_cam = golden_data["cam"]

    sample_mp4 = Path(__file__).parent / "golden" / "gta6_sample_25s.mp4"
    assert sample_mp4.exists()

    res = analyze_facecam(sample_mp4)
    pred_cam = res["cam"]
    assert pred_cam is not None, "A camera box must be detected on the sample"

    score = iou(pred_cam, truth_cam)
    print(f"Facecam IoU score: {score:.3f} (pred: {pred_cam}, truth: {truth_cam})")
    assert score >= 0.80, f"Facecam IoU {score:.3f} is below 0.80 objective"


def test_render_timeline_clip_multi_segment(tmp_path):
    """When a clip spans overlay and gameplay segments, render_timeline_clip concatenates properly."""
    raw = short_clip()
    out = tmp_path / "multi_rendered.mp4"

    timeline = [
        {"start": 0.0, "end": 3.0, "type": "overlay"},
        {"start": 3.0, "end": 6.0, "type": "gameplay"},
    ]
    cam = layouts.Rect(0.7, 0.1, 0.25, 0.25)

    final = render_timeline_clip(
        raw,
        out,
        clip_start=0.0,
        clip_end=6.0,
        timeline=timeline,
        cam=cam,
        fmt="9:16",
    )

    assert final.exists()
    info = ffmpeg.probe(final)
    assert (info.width, info.height) == (1080, 1920)
    assert 5.5 <= info.duration <= 6.5
