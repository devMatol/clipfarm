from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from ..config import settings
from ..db import engine, get_session
from ..models import Clip, Project, ProjectCreateUrl
from ..queue import process_project

router = APIRouter(prefix="/projects", tags=["projects"])


def _compute_id(source: str) -> str:
    return hashlib.sha1(source.encode()).hexdigest()[:10]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    url_data: Optional[ProjectCreateUrl] = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Créer un projet à partir d'une URL vidéo."""
    if not url_data or not url_data.url:
        raise HTTPException(status_code=400, detail="Une URL est requise")

    source_url = url_data.url.strip()
    proj_id = _compute_id(source_url)

    existing = session.get(Project, proj_id)
    if existing and existing.status in ("queued", "ingesting", "transcribing", "analysing", "detecting", "rendering"):
        return {"project": existing, "message": "Projet déjà en cours de traitement"}

    project_settings = {
        "layout": url_data.layout,
        "format": url_data.format,
        "cam": url_data.cam,
        "captions": url_data.captions,
        "max_clips": url_data.max_clips,
        "min_clip_s": url_data.min_clip_s,
        "max_clip_s": url_data.max_clip_s,
        "llm": url_data.llm,
        "skip_if_subtitles_present": url_data.skip_if_subtitles_present,
    }

    if existing:
        existing.status = "queued"
        existing.progress = 0.0
        existing.step = "queued"
        existing.error = None
        existing.settings_json = project_settings
        session.add(existing)
        session.commit()
        session.refresh(existing)
        project = existing
    else:
        project = Project(
            id=proj_id,
            source_url=source_url,
            status="queued",
            progress=0.0,
            step="queued",
            settings_json=project_settings,
        )
        session.add(project)
        session.commit()
        session.refresh(project)

    # Point 1 : Plus aucun except: pass autour de defer()
    try:
        await process_project.defer_async(project_id=proj_id)
    except Exception as exc:
        project.status = "failed"
        project.error = f"Échec de mise en file d'attente du job: {exc}"
        session.add(project)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur mise en file: {exc}",
        )

    return {"project": project}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_project(
    file: UploadFile = File(...),
    layout: str = Form("center"),
    format: str = Form("9:16"),
    cam: Optional[str] = Form(None),
    captions: Optional[str] = Form("punchy"),
    max_clips: int = Form(5),
    min_clip_s: Optional[float] = Form(None),
    max_clip_s: Optional[float] = Form(None),
    llm: Optional[str] = Form(None),
    skip_if_subtitles_present: bool = Form(True),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Upload d'une vidéo en streaming avec nom de fichier unique."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    raw_filename = Path(file.filename or "video.mp4").name

    # Calcul d'un ID temporaire pour le nom unique
    temp_seed = f"{raw_filename}_{file.size or 0}"
    proj_id = _compute_id(temp_seed)

    # Point 8 : Nom de fichier unique (id + nom d'origine)
    filename = f"{proj_id}_{raw_filename}"
    target_path = settings.upload_dir / filename

    chunk_size = 1024 * 1024
    with open(target_path, "wb") as buffer:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            buffer.write(chunk)

    # Calcul ID définitif basé sur le chemin absolu
    proj_id = _compute_id(str(target_path.resolve()))
    cam_dict = None
    if cam:
        try:
            cam_dict = json.loads(cam)
        except Exception:
            try:
                parts = [float(p.strip()) for p in cam.split(",") if p.strip()]
                if len(parts) == 4:
                    cam_dict = {"x": parts[0], "y": parts[1], "w": parts[2], "h": parts[3]}
            except Exception:
                pass

    project_settings = {
        "layout": layout,
        "format": format,
        "cam": cam_dict,
        "captions": captions,
        "max_clips": max_clips,
        "min_clip_s": min_clip_s,
        "max_clip_s": max_clip_s,
        "llm": llm,
        "skip_if_subtitles_present": skip_if_subtitles_present,
    }

    existing = session.get(Project, proj_id)
    if existing:
        existing.source_path = str(target_path.resolve())
        existing.status = "queued"
        existing.progress = 0.0
        existing.step = "queued"
        existing.error = None
        existing.settings_json = project_settings
        session.add(existing)
        session.commit()
        session.refresh(existing)
        project = existing
    else:
        project = Project(
            id=proj_id,
            source_path=str(target_path.resolve()),
            status="queued",
            progress=0.0,
            step="queued",
            settings_json=project_settings,
        )
        session.add(project)
        session.commit()
        session.refresh(project)

    # Point 1 : Pas d'except pass
    try:
        await process_project.defer_async(project_id=proj_id)
    except Exception as exc:
        project.status = "failed"
        project.error = f"Échec de mise en file d'attente du job: {exc}"
        session.add(project)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur mise en file: {exc}",
        )

    return {"project": project}


@router.post("/{id}/set-cam")
async def set_cam(
    id: str,
    cam: dict[str, float],
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Valide ou corrige le cadrage facecam et relance le pipeline."""
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    settings_data = project.settings_json or {}
    settings_data["cam"] = cam
    project.settings_json = settings_data
    project.status = "queued"
    project.step = "queued"
    session.add(project)

    # Mémoriser le preset par chaîne si disponible
    pdir = settings.data_dir / "projects" / id
    meta_file = pdir / "metadata.json"
    if meta_file.exists():
        try:
            m = json.loads(meta_file.read_text(encoding="utf-8"))
            channel = m.get("uploader") or m.get("channel")
            if channel:
                from ..models import CamPreset
                preset = session.exec(select(CamPreset).where(CamPreset.channel == channel)).first()
                if not preset:
                    preset = CamPreset(channel=channel, rect=cam)
                else:
                    preset.rect = cam
                session.add(preset)
        except Exception:
            pass

    session.commit()

    try:
        await process_project.defer_async(project_id=id)
    except Exception as exc:
        project.status = "failed"
        project.error = f"Échec relance job: {exc}"
        session.add(project)
        session.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    return {"project": project, "message": "Cadrage facecam enregistré, suite du traitement lancée."}


@router.get("")
def list_projects(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    projects = session.exec(select(Project).order_by(Project.created_at.desc())).all()
    results = []
    for p in projects:
        data = p.model_dump()
        data["clips_count"] = len(p.clips)
        results.append(data)
    return results


@router.get("/{id}")
def get_project(id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    clips = session.exec(select(Clip).where(Clip.project_id == id).order_by(Clip.final_score.desc())).all()
    data = project.model_dump()
    data["clips"] = [c.model_dump() for c in clips]

    # Détection automatique facecam et timeline lues depuis cam.json si existant
    cam_file = settings.data_dir / "projects" / id / "cam.json"
    if cam_file.exists():
        try:
            cam_data = json.loads(cam_file.read_text(encoding="utf-8"))
            data["detected_cam"] = cam_data.get("cam")
            data["cam_timeline"] = cam_data.get("timeline")
        except Exception:
            pass

    return data


@router.get("/{id}/clips")
def get_project_clips(id: str, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Renvoie la liste des clips pour un projet donné."""
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    clips = session.exec(select(Clip).where(Clip.project_id == id).order_by(Clip.final_score.desc())).all()
    results = []
    for c in clips:
        d = c.model_dump()
        if c.file_path:
            try:
                rel = Path(c.file_path).resolve().relative_to(settings.data_dir.resolve()).as_posix()
                d["video_url"] = f"/media/{rel}"
            except Exception:
                d["video_url"] = None
        results.append(d)
    return results


@router.get("/{id}/events")
async def project_events(id: str):
    """Point 5 : SSE lisant l'état en base chaque seconde pour supporter le worker multi-processus."""
    async def sse_wrapper():
        last_signature = None
        while True:
            with Session(engine) as session:
                project = session.get(Project, id)
                if not project:
                    break
                current_signature = (project.status, project.step, round(project.progress, 2), project.error)
                if current_signature != last_signature:
                    last_signature = current_signature
                    payload = json.dumps({
                        "project_id": project.id,
                        "step": project.step,
                        "progress": project.progress,
                        "message": f"{project.step} ({int(project.progress * 100)}%)",
                        "status": project.status,
                        "error": project.error,
                    })
                    yield f"event: progress\ndata: {payload}\n\n"

                if project.status in ("ready", "failed"):
                    break
            await asyncio.sleep(1.0)

    return StreamingResponse(
        sse_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{id}/extract-frame")
def extract_frame(
    id: str,
    time_s: float = 5.0,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    source_file = None
    if project.source_path and Path(project.source_path).is_file():
        source_file = Path(project.source_path)
    else:
        candidate = settings.data_dir / "projects" / id / "source.mp4"
        if candidate.is_file():
            source_file = candidate

    if not source_file or not source_file.exists():
        raise HTTPException(
            status_code=400,
            detail="La vidéo source n'est pas encore disponible localement",
        )

    out_dir = settings.data_dir / "projects" / id
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_path = out_dir / f"frame_{int(time_s)}.jpg"

    if not frame_path.exists():
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(time_s),
            "-i",
            str(source_file),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(frame_path),
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            raise HTTPException(status_code=500, detail="Échec de l'extraction de l'image")

    rel_path = frame_path.relative_to(settings.data_dir.resolve()).as_posix()
    return {"url": f"/media/{rel_path}"}


@router.post("/{id}/retry")
async def retry_project(id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    project.status = "queued"
    project.progress = 0.0
    project.step = "queued"
    project.error = None
    session.add(project)
    session.commit()
    session.refresh(project)

    try:
        await process_project.defer_async(project_id=id)
    except Exception as exc:
        project.status = "failed"
        project.error = f"Échec de mise en file: {exc}"
        session.add(project)
        session.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    return {"project": project, "message": "Projet remis en file d'attente"}


@router.delete("/{id}")
async def delete_project(id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    # 1. Supprimer les clips associés dans la base de données
    clips = session.exec(select(Clip).where(Clip.project_id == id)).all()
    for c in clips:
        session.delete(c)

    # 2. Supprimer le projet en base de données
    session.delete(project)
    session.commit()

    # 3. Nettoyer les fichiers sur le disque (data/projects/<id>)
    project_dir = settings.data_dir / "projects" / id
    if project_dir.exists() and project_dir.is_dir():
        import shutil
        try:
            shutil.rmtree(project_dir, ignore_errors=True)
        except Exception:
            pass

    return {"ok": True, "message": f"Projet #{id} supprimé avec succès"}

