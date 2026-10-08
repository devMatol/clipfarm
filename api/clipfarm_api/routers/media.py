from __future__ import annotations

import os
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse, FileResponse
from ..config import settings

router = APIRouter(prefix="/media", tags=["media"])


def _safe_resolve(requested_path: str) -> Path:
    # Nettoyer et résoudre le chemin
    clean_subpath = Path(requested_path).as_posix().lstrip("/\\")
    full_path = (settings.data_dir / clean_subpath).resolve()
    # Sécurité : vérifier que le fichier reste strictement dans settings.data_dir
    try:
        full_path.relative_to(settings.data_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès non autorisé")
    return full_path


@router.get("/{path:path}")
async def serve_media(path: str, request: Request) -> Response:
    file_path = _safe_resolve(path)
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier introuvable")

    file_size = file_path.stat().st_size
    content_type, _ = mimetypes.guess_type(str(file_path))
    content_type = content_type or "application/octet-stream"

    # Gestion de l'en-tête Range pour la lecture vidéo partielle (seek)
    range_header = request.headers.get("range")
    if not range_header or not content_type.startswith("video/"):
        return FileResponse(file_path, media_type=content_type)

    try:
        # Range format: bytes=start-end
        range_val = range_header.strip().replace("bytes=", "")
        start_str, _, end_str = range_val.partition("-")
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        end = min(end, file_size - 1)
        chunk_size = end - start + 1
    except Exception:
        return FileResponse(file_path, media_type=content_type)

    def file_chunk_generator():
        with open(file_path, "rb") as f:
            f.seek(start)
            bytes_left = chunk_size
            while bytes_left > 0:
                read_size = min(64 * 1024, bytes_left)
                data = f.read(read_size)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": content_type,
    }
    return StreamingResponse(
        file_chunk_generator(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers=headers,
    )
