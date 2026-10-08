"""Détection de sous-titres incrustés via RapidOCR sur le tiers inférieur de la vidéo.

Échantillonne 10 images réparties sur le clip et analyse le tiers bas (y >= 66%).
Si du texte est détecté sur au moins 6 images, les sous-titres sont considérés comme déjà incrustés.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ..media import ffmpeg


def check_burned_subtitles_in_image(img_path: str | Path, ocr_instance: Any = None) -> bool:
    """Analyse le tiers bas d'une image pour détecter la présence de texte incrusté."""
    import cv2

    if ocr_instance is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            ocr_instance = RapidOCR()
        except Exception:
            return False

    img = cv2.imread(str(img_path))
    if img is None:
        return False

    ih, iw, _ = img.shape
    if ih < 30 or iw < 30:
        return False

    # Tiers bas de l'écran (y de 66% à 100%)
    bottom_crop = img[int(ih * 0.66) :, :]
    try:
        results, _ = ocr_instance(bottom_crop)
        # results est une liste de [box, text, score]
        if results and len(results) > 0:
            for item in results:
                # Vérifier score de confiance et longueur du texte
                if len(item) >= 3:
                    text = str(item[1]).strip()
                    score = float(item[2])
                    if len(text) >= 2 and score >= 0.40:
                        return True
    except Exception:
        return False

    return False


def detect_burned_in_subtitles(
    video_path: str | Path,
    start: float,
    end: float,
    sample_count: int = 10,
    threshold: int = 6,
) -> tuple[bool, int]:
    """Extrait sample_count images réparties sur l'intervalle [start, end] et applique RapidOCR sur le tiers bas.

    Retourne (has_burned_subs, detected_count).
    """
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        return False, 0

    duration = max(0.1, end - start)
    timestamps = [start + (i + 0.5) * (duration / sample_count) for i in range(sample_count)]

    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
    except Exception:
        # Repli gracieux si RapidOCR non disponible
        return False, 0

    detected_count = 0

    with tempfile.TemporaryDirectory(prefix="clipfarm_ocr_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        for idx, ts in enumerate(timestamps):
            frame_file = tmp_path / f"frame_{idx:02d}.jpg"
            try:
                # Extraction rapide d'une frame précise en taille 640px
                ffmpeg.run([
                    "-ss", f"{ts:.2f}",
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-vf", "scale=640:-2",
                    "-q:v", "2",
                    str(frame_file),
                ])
                if frame_file.exists():
                    has_text = check_burned_subtitles_in_image(frame_file, ocr_instance=ocr)
                    if has_text:
                        detected_count += 1
            except Exception:
                continue

    return (detected_count >= threshold), detected_count
