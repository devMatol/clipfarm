from unittest.mock import MagicMock, patch

from clipfarm_engine.media.face_detect import check_face_in_region
from clipfarm_engine.media.layouts import Rect

from media_samples import short_clip


def test_face_absent_returns_false():
    """Synthetic clip with uniform colors has no face: check_face_in_region must return False."""
    cam = Rect(0.1, 0.1, 0.3, 0.3)
    has_face = check_face_in_region(short_clip(), cam)
    assert has_face is False


def test_face_none_cam_returns_true():
    """When cam is None, check_face_in_region returns True (no fallback forced)."""
    assert check_face_in_region(short_clip(), None) is True


def test_face_present_returns_true_with_detection():
    """When a face detection is found, check_face_in_region returns True."""
    cam = Rect(0.1, 0.1, 0.3, 0.3)

    mock_detection = MagicMock()
    mock_detection.detections = [MagicMock()]

    with patch("mediapipe.solutions.face_detection.FaceDetection") as mock_fd_cls:
        mock_instance = MagicMock()
        mock_instance.process.return_value = mock_detection
        mock_fd_cls.return_value.__enter__.return_value = mock_instance

        has_face = check_face_in_region(short_clip(), cam)
        assert has_face is True


def test_render_all_falls_back_to_center_when_no_face(tmp_path):
    """When rendering with facecam_top on a video without face, it falls back to center and marks face_fallback=True."""
    from clipfarm_engine.highlights.llm import Candidate
    from clipfarm_engine.pipeline import Project, RenderOptions, render_all

    p = Project(id="test-proj", dir=tmp_path, source=short_clip())
    cands = [Candidate(start=0.0, end=4.0, final_score=0.9, title="Test", hook="Hook", reason="Test")]
    opts = RenderOptions(layout="facecam_top", cam=Rect(0.1, 0.1, 0.3, 0.3), captions=None)

    rendered = render_all(p, cands, [], opts, progress=lambda *a: None)
    assert len(rendered) == 1
    assert rendered[0]["layout"] == "center"
    assert rendered[0]["face_fallback"] is True

