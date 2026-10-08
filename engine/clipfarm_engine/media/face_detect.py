"""Face detection validation using MediaPipe.

Verifies that a face is visible within a camera region across multiple frames.
Falls back safely if MediaPipe is not installed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .layouts import Rect


def check_face_in_region(
    video_path: str | Path,
    cam: Rect | None,
    num_samples: int = 3,
    min_confidence: float = 0.5,
) -> bool:
    """Check if a face is detected within `cam` bounding box in at least 1 of `num_samples` frames.

    If cam is None or MediaPipe / cv2 cannot be loaded, returns True (no fallback forced).
    """
    if cam is None:
        return True

    try:
        import cv2
        import mediapipe as mp
        from ..vision.shim import install_solutions_shim
        install_solutions_shim()
    except ImportError:
        # Si mediapipe / cv2 non installés, ne bloque pas le pipeline
        return True

    from . import ffmpeg

    video_path = Path(video_path).resolve()
    info = ffmpeg.probe(video_path)
    if info.duration <= 0.1:
        return True

    # 3 points temporels dans le clip : 20%, 50%, 80%
    timestamps = [info.duration * ratio for ratio in (0.2, 0.5, 0.8)][:num_samples]

    faces_found = 0
    with tempfile.TemporaryDirectory(prefix="clipfarm_face_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        with mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=min_confidence
        ) as detector:
            for idx, t in enumerate(timestamps):
                frame_img_path = tmp_path / f"frame_{idx}.jpg"
                try:
                    ffmpeg.frame_at(video_path, t, frame_img_path)
                    if not frame_img_path.exists():
                        continue

                    img = cv2.imread(str(frame_img_path))
                    if img is None:
                        continue

                    ih, iw, _ = img.shape
                    # Coordonnées pixels du rectangle cam
                    x, y, w, h = cam.to_px(iw, ih)
                    if w <= 10 or h <= 10:
                        continue

                    crop = img[y : y + h, x : x + w]
                    if crop.size == 0:
                        continue

                    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    results = detector.process(rgb)

                    if results and results.detections:
                        faces_found += 1
                except Exception:
                    continue

    # Considéré valide si au moins 1 frame sur 3 montre un visage
    return faces_found > 0
