"""Automatic facecam detection and timeline classification.

Uses MediaPipe Face Detection + OpenCV contours/edge profiling to:
1. Sample video frames every 2 seconds.
2. Detect faces across full image (fullscreen) and corner regions (overlay).
3. Classify each frame into:
   - "overlay": small face (< 18% width) near a border.
   - "fullscreen": large face (>= 18% width) or centered.
   - "gameplay": no face detected.
4. Cluster overlay face detections to find the streamer's stable camera position.
5. Detect the exact camera frame (via OpenCV edge profiling) or fall back to an aspect-ratio box.
6. Generate a temporal timeline of layout segments and write cam.json.
"""

from __future__ import annotations

import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..media import ffmpeg
from .shim import install_solutions_shim

install_solutions_shim()


@dataclass
class FaceBox:
    x: float
    y: float
    w: float
    h: float
    confidence: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def is_in_corner(cx: float, cy: float) -> bool:
    """Check if face center is within 30% of a horizontal AND vertical border.

    Specifically:
    - Horizontal: cx < 0.30 or cx > 0.70
    - Vertical: cy < 0.30 or cy > 0.70
    Both conditions must be met simultaneously (never in the center).
    """
    near_h = (cx < 0.30) or (cx > 0.70)
    near_v = (cy < 0.30) or (cy > 0.70)
    return near_h and near_v


def is_near_border(x: float, y: float, w: float, h: float) -> bool:
    """Backward compatibility alias checking corner placement."""
    cx = x + w / 2
    cy = y + h / 2
    return is_in_corner(cx, cy)


def detect_faces_in_image(img: np.ndarray, detector: Any) -> list[FaceBox]:
    """Detect faces across the full image as well as in the 4 screen corners."""
    import cv2

    ih, iw, _ = img.shape
    found_faces: list[FaceBox] = []

    # 1. Détection sur image globale (pour plein écran)
    small_full = cv2.resize(img, (640, int(640 * ih / iw)))
    rgb_full = cv2.cvtColor(small_full, cv2.COLOR_BGR2RGB)
    res_full = detector.process(rgb_full)

    if res_full and res_full.detections:
        for det in res_full.detections:
            bb = det.location_data.relative_bounding_box
            score = float(det.score[0]) if det.score else 0.5
            found_faces.append(
                FaceBox(
                    x=max(0.0, float(bb.xmin)),
                    y=max(0.0, float(bb.ymin)),
                    w=min(1.0, float(bb.width)),
                    h=min(1.0, float(bb.height)),
                    confidence=score,
                )
            )

    # 2. Détection ciblée dans les 4 coins (overlay streamer webcam)
    # [xmin, ymin, xmax, ymax]
    corners = [
        (0.60, 0.00, 1.00, 0.50),  # Haut droite
        (0.00, 0.00, 0.40, 0.50),  # Haut gauche
        (0.60, 0.50, 1.00, 1.00),  # Bas droite
        (0.00, 0.50, 0.40, 1.00),  # Bas gauche
    ]

    for c_xmin, c_ymin, c_xmax, c_ymax in corners:
        x1, y1 = int(c_xmin * iw), int(c_ymin * ih)
        x2, y2 = int(c_xmax * iw), int(c_ymax * ih)
        crop = img[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        res_crop = detector.process(rgb_crop)
        if res_crop and res_crop.detections:
            for det in res_crop.detections:
                bb = det.location_data.relative_bounding_box
                score = float(det.score[0]) if det.score else 0.5
                gx = c_xmin + float(bb.xmin) * (c_xmax - c_xmin)
                gy = c_ymin + float(bb.ymin) * (c_ymax - c_ymin)
                gw = float(bb.width) * (c_xmax - c_xmin)
                gh = float(bb.height) * (c_ymax - c_ymin)
                found_faces.append(
                    FaceBox(
                        x=max(0.0, gx),
                        y=max(0.0, gy),
                        w=min(1.0, gw),
                        h=min(1.0, gh),
                        confidence=score,
                    )
                )

    return found_faces


def classify_frame(faces: list[FaceBox]) -> tuple[str, FaceBox | None]:
    """Classify a frame as 'overlay', 'fullscreen', or 'gameplay'."""
    if not faces:
        return "gameplay", None

    # Visage principal avec la plus forte confiance
    faces_sorted = sorted(faces, key=lambda f: f.confidence, reverse=True)
    primary = faces_sorted[0]

    # Overlay : petit visage (< 20% de largeur) situé STRICTEMENT dans un coin (jamais au centre)
    if primary.w < 0.20 and is_in_corner(primary.cx, primary.cy):
        return "overlay", primary

    # Fullscreen : visage plus grand ou centré
    return "fullscreen", primary


def cluster_overlays(overlay_faces: list[FaceBox], max_distance: float = 0.15) -> list[FaceBox]:
    """Cluster overlay faces by center proximity and return the largest cluster."""
    if not overlay_faces:
        return []

    clusters: list[list[FaceBox]] = []
    for f in overlay_faces:
        matched = False
        for c in clusters:
            med_cx = sum(x.cx for x in c) / len(c)
            med_cy = sum(x.cy for x in c) / len(c)
            dist = math.hypot(f.cx - med_cx, f.cy - med_cy)
            if dist <= max_distance:
                c.append(f)
                matched = True
                break
        if not matched:
            clusters.append([f])

    clusters.sort(key=len, reverse=True)
    return clusters[0] if clusters else []


def find_camera_frame_edges(img: np.ndarray, face: FaceBox) -> list[float] | None:
    """Find rectangular camera frame edges surrounding the face using OpenCV edge gradients."""
    import cv2

    ih, iw, _ = img.shape

    # Région d'analyse autour du visage
    rx1 = max(0, int((face.cx - face.w * 2.5) * iw))
    ry1 = max(0, int((face.cy - face.h * 1.5) * ih))
    rx2 = min(iw, int((face.cx + face.w * 2.5) * iw))
    ry2 = min(ih, int((face.cy + face.h * 2.0) * ih))

    crop = img[ry1:ry2, rx1:rx2]
    if crop.size == 0 or crop.shape[0] < 20 or crop.shape[1] < 20:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)

    # Profils de sommation de gradients par colonne et par ligne
    col_profile = np.sum(edges, axis=0)
    row_profile = np.sum(edges, axis=1)

    max_col = np.max(col_profile) if np.max(col_profile) > 0 else 1.0
    max_row = np.max(row_profile) if np.max(row_profile) > 0 else 1.0

    fx_in_crop = int(face.x * iw) - rx1
    fx_end_in_crop = int((face.x + face.w) * iw) - rx1
    fy_in_crop = int(face.y * ih) - ry1
    fy_end_in_crop = int((face.y + face.h) * ih) - ry1

    # Bord gauche : pic de gradient le plus proche du visage sur sa gauche (à une distance raisonnable)
    left_picks = [x for x in range(0, max(0, fx_in_crop)) if col_profile[x] > 0.35 * max_col]
    # Bord droit : pic de gradient à droite du visage
    right_picks = [x for x in range(min(crop.shape[1], fx_end_in_crop), crop.shape[1]) if col_profile[x] > 0.35 * max_col]
    # Bord haut : pic au-dessus du visage
    top_picks = [y for y in range(0, max(0, fy_in_crop)) if row_profile[y] > 0.35 * max_row]
    # Bord bas : pic en-dessous du visage
    bottom_picks = [y for y in range(min(crop.shape[0], fy_end_in_crop), crop.shape[0]) if row_profile[y] > 0.35 * max_row]

    if left_picks and right_picks and top_picks and bottom_picks:
        # Prendre la frontière extérieure
        bx1 = rx1 + left_picks[0]
        bx2 = rx1 + right_picks[-1]
        by1 = ry1 + top_picks[0]
        by2 = ry1 + bottom_picks[-1]

        bw = bx2 - bx1
        bh = by2 - by1

        rel_x = bx1 / iw
        rel_y = by1 / ih
        rel_w = bw / iw
        rel_h = bh / ih

        aspect = rel_w / max(rel_h, 1e-4)
        if 0.8 <= aspect <= 2.2 and rel_w >= face.w * 1.5 and rel_h >= face.h * 1.3:
            return [round(rel_x, 3), round(rel_y, 3), round(rel_w, 3), round(rel_h, 3)]

    return None


def fallback_box(face: FaceBox, aspect: float = 1.0) -> list[float]:
    """Compute a centered camera box encompassing the face with headroom and shoulders."""
    cw = max(0.22, min(0.35, face.w * 3.5))
    ch = cw / aspect
    if ch > 0.35:
        ch = 0.30
        cw = ch * aspect

    cx = max(0.0, min(1.0 - cw, face.cx - cw / 2))
    cy = max(0.0, min(1.0 - ch, face.cy - ch * 0.45))
    return [round(cx, 3), round(cy, 3), round(cw, 3), round(ch, 3)]


def smooth_timeline(timeline: list[dict[str, Any]], min_duration: float = 8.0) -> list[dict[str, Any]]:
    """Remove short flickers in the timeline by merging segments smaller than min_duration (default 8s)."""
    if len(timeline) <= 1:
        return timeline

    smoothed = list(timeline)
    i = 0
    while i < len(smoothed):
        seg = smoothed[i]
        dur = seg["end"] - seg["start"]
        if dur < min_duration and len(smoothed) > 1:
            if i > 0:
                smoothed[i - 1]["end"] = seg["end"]
                smoothed.pop(i)
                continue
            elif i + 1 < len(smoothed):
                smoothed[i + 1]["start"] = seg["start"]
                smoothed.pop(i)
                continue
        i += 1

    merged: list[dict[str, Any]] = []
    for s in smoothed:
        if merged and merged[-1]["type"] == s["type"]:
            merged[-1]["end"] = s["end"]
        else:
            merged.append(dict(s))
    return merged


def limit_clip_transitions(
    active_segments: list[tuple[float, float, str]],
    max_transitions: int = 2,
) -> list[tuple[float, float, str]]:
    """Garantit au maximum max_transitions (ex: 2 changements = 3 sous-segments max).

    Si plus de 2 transitions, fusionne itérativement le sous-segment le plus court
    avec son voisin dominant.
    """
    if len(active_segments) <= max_transitions + 1:
        return active_segments

    segs = list(active_segments)
    while len(segs) > max_transitions + 1:
        shortest_idx = min(range(len(segs)), key=lambda idx: segs[idx][1] - segs[idx][0])
        if shortest_idx > 0:
            target_idx = shortest_idx - 1
            prev_s, prev_e, prev_t = segs[target_idx]
            cur_s, cur_e, _ = segs.pop(shortest_idx)
            segs[target_idx] = (prev_s, cur_e, prev_t)
        else:
            cur_s, cur_e, _ = segs.pop(0)
            next_s, next_e, next_t = segs[0]
            segs[0] = (cur_s, next_e, next_t)

    merged = [segs[0]]
    for s_start, s_end, s_type in segs[1:]:
        if s_type == merged[-1][2]:
            merged[-1] = (merged[-1][0], s_end, s_type)
        else:
            merged.append((s_start, s_end, s_type))
    return merged


def analyze_facecam(
    video_path: str | Path,
    project_dir: Path | None = None,
    step_s: float = 2.0,
) -> dict[str, Any]:
    """Analyze video frames every `step_s` seconds, locate facecam overlay, and compute timeline.

    Outputs cam.json in project_dir if given.
    """
    import cv2
    import mediapipe as mp

    video_path = Path(video_path).resolve()
    info = ffmpeg.probe(video_path)
    total_duration = max(info.duration, 0.1)

    frame_records: list[dict[str, Any]] = []
    overlay_faces: list[FaceBox] = []
    sample_images: dict[int, Path] = {}

    with tempfile.TemporaryDirectory(prefix="clipfarm_facecam_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Extraction d'une image toutes les step_s secondes
        fps_expr = f"1/{step_s}" if step_s >= 1.0 else f"{1.0 / step_s:.2f}"
        out_pattern = tmp_path / "frame_%04d.jpg"
        ffmpeg.run([
            "-i", str(video_path),
            "-vf", f"fps={fps_expr}",
            "-q:v", "2",
            str(out_pattern),
        ])

        frame_files = sorted(tmp_path.glob("frame_*.jpg"))

        with mp.solutions.face_detection.FaceDetection(
            min_detection_confidence=0.35,
            model_selection=0,
        ) as detector:
            for idx, frame_file in enumerate(frame_files):
                timestamp = idx * step_s
                if timestamp > total_duration:
                    break

                img = cv2.imread(str(frame_file))
                if img is None:
                    continue

                faces = detect_faces_in_image(img, detector)
                frame_type, primary_face = classify_frame(faces)
                frame_records.append({
                    "time": timestamp,
                    "type": frame_type,
                    "face": primary_face,
                })

                if frame_type == "overlay" and primary_face:
                    overlay_faces.append(primary_face)
                    sample_images[idx] = frame_file

        # Stabilisation de la facecam
        best_cluster = cluster_overlays(overlay_faces)
        cam_rect = None

        if best_cluster:
            med_x = sorted(f.x for f in best_cluster)[len(best_cluster) // 2]
            med_y = sorted(f.y for f in best_cluster)[len(best_cluster) // 2]
            med_w = sorted(f.w for f in best_cluster)[len(best_cluster) // 2]
            med_h = sorted(f.h for f in best_cluster)[len(best_cluster) // 2]
            stable_face = FaceBox(med_x, med_y, med_w, med_h, confidence=0.9)

            first_sample = list(sample_images.values())[0] if sample_images else None
            if first_sample:
                sample_img = cv2.imread(str(first_sample))
                if sample_img is not None:
                    detected_edges = find_camera_frame_edges(sample_img, stable_face)
                    if detected_edges:
                        cam_rect = detected_edges

            if cam_rect is None:
                cam_rect = fallback_box(stable_face, aspect=1.0)

        # Construction de la timeline temporelle
        raw_timeline: list[dict[str, Any]] = []
        if frame_records:
            cur_type = frame_records[0]["type"]
            cur_start = 0.0

            for i in range(1, len(frame_records)):
                rec = frame_records[i]
                if rec["type"] != cur_type:
                    raw_timeline.append({
                        "start": round(cur_start, 2),
                        "end": round(rec["time"], 2),
                        "type": cur_type,
                    })
                    cur_type = rec["type"]
                    cur_start = rec["time"]

            raw_timeline.append({
                "start": round(cur_start, 2),
                "end": round(total_duration, 2),
                "type": cur_type,
            })
        else:
            raw_timeline = [{"start": 0.0, "end": round(total_duration, 2), "type": "gameplay"}]

        timeline = smooth_timeline(raw_timeline, min_duration=8.0)

        # Garde-fou 40% overlay : le mode facecam ne s'active que si overlay couvre au moins 40% de la vidéo
        overlay_duration = sum(
            float(s["end"]) - float(s["start"])
            for s in timeline
            if s["type"] == "overlay"
        )
        overlay_ratio = overlay_duration / max(total_duration, 0.1)

        if overlay_ratio < 0.40:
            cam_rect = None
            for seg in timeline:
                if seg["type"] == "overlay":
                    seg["type"] = "fullscreen"
            timeline = smooth_timeline(timeline, min_duration=8.0)

        result = {
            "cam": cam_rect,
            "timeline": timeline,
            "overlay_ratio": round(overlay_ratio, 3),
        }

        if project_dir is not None:
            project_dir = Path(project_dir)
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "cam.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )

        return result
