from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from clipfarm_engine.media.ffmpeg import probe, MediaInfo


def sanitize_video_for_publishing(input_path: Path, output_path: Path) -> Path:
    """
    Supprime toutes les métadonnées techniques et personnelles (GPS, modèle caméra, nom de PC, logiciel),
    assure le flag faststart pour le streaming web et copie les flux sans réencodage inutile.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
        "-map_metadata",
        "-1",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"Échec du nettoyage des métadonnées vidéo : {proc.stderr}")

    return output_path


def check_video_for_platform(path: Path, max_duration_s: float = 60.0, allow_square: bool = True) -> tuple[bool, list[str]]:
    """Vérifie la conformité technique du fichier vidéo avec ffprobe."""
    errors: list[str] = []
    try:
        info = probe(path)
    except Exception as exc:
        return False, [f"Impossible d'analyser le fichier vidéo avec ffprobe : {exc}"]

    if info.duration > (max_duration_s + 1.0):
        errors.append(f"La durée du fichier ({info.duration:.1f}s) dépasse la limite autorisée ({max_duration_s:.1f}s).")

    # Ratio d'aspect : vertical 9:16 (0.5625) ou carré 1:1 si autorisé
    ratio = info.width / info.height if info.height > 0 else 1.0
    is_vertical = ratio <= 0.65  # 9:16 ou proche
    is_square = 0.95 <= ratio <= 1.05

    if not is_vertical and not (allow_square and is_square):
        errors.append(f"Le format ({info.width}x{info.height}, ratio {ratio:.2f}) n'est ni vertical (9:16) ni carré (1:1).")

    if not info.has_audio:
        errors.append("Le fichier ne contient aucune piste audio.")

    return len(errors) == 0, errors
