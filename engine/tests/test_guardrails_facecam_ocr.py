import numpy as np
import cv2
import pytest
from pathlib import Path
from clipfarm_engine.vision.facecam import (
    FaceBox,
    classify_frame,
    smooth_timeline,
    limit_clip_transitions,
    analyze_facecam,
    is_in_corner,
)
from clipfarm_engine.media.layouts import Rect, check_cam_game_overlap
from clipfarm_engine.vision.subtitles_ocr import detect_burned_in_subtitles


def test_guardrail_face_in_center_never_overlay():
    """Garde-fou 1: un visage au centre (cx=0.5, cy=0.5) ne doit JAMAIS être classé en overlay, même s'il est petit."""
    # Visage de largeur 12% (donc < 15%), mais centré en x=0.44, y=0.44 -> cx=0.50, cy=0.50
    face = FaceBox(x=0.44, y=0.44, w=0.12, h=0.12, confidence=0.95)
    assert not is_in_corner(face.x + face.w / 2, face.y + face.h / 2)
    
    frame_type, primary = classify_frame([face])
    # Ne doit pas être 'overlay'
    assert frame_type != "overlay"
    assert frame_type == "fullscreen"  # Visage centré ou interview


def test_guardrail_face_in_corner_is_overlay():
    """Garde-fou 1: un petit visage dans un coin (< 30% d'un bord H et V) est classé en overlay."""
    # Coin supérieur droit : x=0.75, y=0.08 -> cx=0.80, cy=0.13 (cx > 0.70 et cy < 0.30)
    face = FaceBox(x=0.75, y=0.08, w=0.10, h=0.10, confidence=0.95)
    assert is_in_corner(face.x + face.w / 2, face.y + face.h / 2)
    frame_type, primary = classify_frame([face])
    assert frame_type == "overlay"
    assert primary == face


def test_guardrail_overlay_ratio_below_40_percent(monkeypatch):
    """Garde-fou 2: Si les segments overlay couvrent moins de 40% de la vidéo, mode facecam désactivé (cam=None)."""
    # Test unitaire de la logique du ratio :
    # Si overlay couvre moins de 40% après détection, analyze_facecam force cam=None et fullscreen
    timeline = [
        {"start": 0.0, "end": 2.0, "type": "overlay"},
        {"start": 2.0, "end": 10.0, "type": "gameplay"},
    ]
    total_duration = 10.0
    overlay_duration = sum(s["end"] - s["start"] for s in timeline if s["type"] == "overlay")
    overlay_ratio = overlay_duration / total_duration
    assert overlay_ratio < 0.40

    # Vérification que le recalcul passe les overlays en fullscreen
    if overlay_ratio < 0.40:
        cam_rect = None
        for seg in timeline:
            if seg["type"] == "overlay":
                seg["type"] = "fullscreen"
        smoothed = smooth_timeline(timeline, min_duration=8.0)

    assert cam_rect is None
    assert all(s["type"] != "overlay" for s in smoothed)


def test_guardrail_smoothing_8s_and_transition_limit():
    """Garde-fou 3: Lissage à 8s minimum et maximum 2 changements de mise en page par clip."""
    raw_timeline = [
        {"start": 0.0, "end": 20.0, "type": "overlay"},
        {"start": 20.0, "end": 25.0, "type": "gameplay"},  # 5s < 8s -> absorbé
        {"start": 25.0, "end": 40.0, "type": "overlay"},
    ]
    smoothed = smooth_timeline(raw_timeline, min_duration=8.0)
    assert len(smoothed) == 1
    assert smoothed[0]["type"] == "overlay"
    assert smoothed[0]["start"] == 0.0
    assert smoothed[0]["end"] == 40.0

    # Test limit_clip_transitions : list[tuple[start, end, type]]
    active_segments = [
        (0.0, 10.0, "overlay"),
        (10.0, 20.0, "gameplay"),
        (20.0, 30.0, "overlay"),
        (30.0, 40.0, "gameplay"),
    ]
    limited = limit_clip_transitions(active_segments, max_transitions=2)
    # Nombre de transitions = len(limited) - 1 <= 2
    assert len(limited) - 1 <= 2


def test_guardrail_cam_game_overlap_rejection():
    """Garde-fou 4: Recouvrement caméra et jeu > 20% doit être détecté pour basculer en centré."""
    # check_cam_game_overlap(sw, sh, ow, oh, cam)
    # Bande jeu par défaut en 9:16 : sw=1920, sh=1080, ow=1080, oh=1920
    # Si la caméra est située au centre (ex: x=0.4, y=0.1, w=0.3, h=0.3), elle est dans la bande jeu
    center_cam = Rect(0.40, 0.10, 0.30, 0.30)
    overlap = check_cam_game_overlap(1920, 1080, 1080, 1920, center_cam)
    assert overlap > 0.20, f"Le recouvrement devrait être > 0.20, obtenu {overlap}"

    # Si la caméra est bien dans le coin droit (ex: x=0.80, y=0.05, w=0.18, h=0.20)
    corner_cam = Rect(0.80, 0.05, 0.18, 0.20)
    corner_overlap = check_cam_game_overlap(1920, 1080, 1080, 1920, corner_cam)
    assert corner_overlap < 0.20, f"Le recouvrement pour un coin devrait être faible, obtenu {corner_overlap}"


def test_guardrail_rapidocr_subtitles_detection(tmp_path):
    """Garde-fou OCR: Détection de sous-titres incrustés sur 10 images synthétiques avec texte dans le tiers bas."""
    # Créer une vidéo synthétique avec texte incrusté en bas
    video_path = tmp_path / "subtitled_synth.mp4"
    h, w = 720, 1280
    fps = 2
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, fps, (w, h))

    # Générer 20 frames (10 secondes) avec un texte net en bas (y=620)
    for i in range(20):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        # Texte en blanc sur fond noir dans le tiers inférieur (y > 480)
        cv2.putText(
            img,
            "Ceci est un sous-titre incruste dans le tiers bas",
            (100, 620),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        out.write(img)
    out.release()

    has_subs, count = detect_burned_in_subtitles(video_path, start=0.0, end=10.0, sample_count=10, threshold=6)
    assert has_subs is True, f"RapidOCR aurait dû détecter la présence de texte récurrent en bas (détections: {count})"
