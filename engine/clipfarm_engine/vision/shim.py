"""MediaPipe compatibility shim for mp.solutions.face_detection.FaceDetection.

Allows code using the legacy `mp.solutions.face_detection.FaceDetection` API
to transparently run on MediaPipe Tasks `FaceDetector` with the local TFLite model.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import numpy as np

MODEL_PATH = Path(__file__).resolve().parent / "blaze_face_short_range.tflite"


class _RelativeBox:
    def __init__(self, xmin: float, ymin: float, width: float, height: float):
        self.xmin = xmin
        self.ymin = ymin
        self.width = width
        self.height = height


class _LocationData:
    def __init__(self, bb: _RelativeBox):
        self.relative_bounding_box = bb


class _DetectionItem:
    def __init__(self, bb: _RelativeBox, score: float):
        self.location_data = _LocationData(bb)
        self.score = [score]


class _ProcessResult:
    def __init__(self, detections: list[_DetectionItem]):
        self.detections = detections


class ShimFaceDetection:
    """Drop-in context manager replacing mp.solutions.face_detection.FaceDetection."""

    def __init__(self, min_detection_confidence: float = 0.5, model_selection: int = 0):
        self.min_confidence = min_detection_confidence
        self._detector = None
        self._init_detector()

    def _init_detector(self):
        try:
            import mediapipe as mp
            from mediapipe.tasks.python.core.base_options import BaseOptions
            from mediapipe.tasks.python.vision import FaceDetector, FaceDetectorOptions

            if not MODEL_PATH.exists():
                return

            options = FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
                min_detection_confidence=self.min_confidence,
            )
            self._detector = FaceDetector.create_from_options(options)
        except Exception:
            self._detector = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._detector:
            try:
                self._detector.close()
            except Exception:
                pass
            self._detector = None

    def process(self, rgb_image: np.ndarray) -> _ProcessResult:
        if self._detector is None:
            return _ProcessResult([])

        try:
            import mediapipe as mp

            h, w, _ = rgb_image.shape
            if h <= 0 or w <= 0:
                return _ProcessResult([])

            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            res = self._detector.detect(mp_img)
            out_items = []
            for d in res.detections:
                bb = d.bounding_box
                score = float(d.categories[0].score) if d.categories else 0.5
                rel_box = _RelativeBox(
                    xmin=bb.origin_x / w,
                    ymin=bb.origin_y / h,
                    width=bb.width / w,
                    height=bb.height / h,
                )
                out_items.append(_DetectionItem(rel_box, score))
            return _ProcessResult(out_items)
        except Exception:
            return _ProcessResult([])


def install_solutions_shim():
    """Ensure `mediapipe.solutions.face_detection.FaceDetection` is importable."""
    try:
        import mediapipe as mp

        if not hasattr(mp, "solutions"):
            solutions_mod = types.ModuleType("mediapipe.solutions")
            face_detection_mod = types.ModuleType("mediapipe.solutions.face_detection")
            face_detection_mod.FaceDetection = ShimFaceDetection

            solutions_mod.face_detection = face_detection_mod
            mp.solutions = solutions_mod

            sys.modules["mediapipe.solutions"] = solutions_mod
            sys.modules["mediapipe.solutions.face_detection"] = face_detection_mod
    except Exception:
        pass
