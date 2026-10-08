from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Clip, ClipRenderRequest, ClipUpdate, Project, ProjectRenderRequest
from ..queue import rerender_project_task
from ..words import resolve_clip_words, regenerate_clip_words, deduplicate_words

router = APIRouter(tags=["clips"])


@router.get("/clips/{id}")
def get_clip(id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    if clip.status == "rendering" and clip.file_path and Path(clip.file_path).is_file():
        try:
            if Path(clip.file_path).stat().st_size > 100_000:
                clip.status = "ready"
                session.add(clip)
                session.commit()
                session.refresh(clip)
        except Exception:
            pass

    data = clip.model_dump()
    if clip.file_path:
        try:
            rel = Path(clip.file_path).resolve().relative_to(settings.data_dir.resolve()).as_posix()
            data["video_url"] = f"/media/{rel}"
        except Exception:
            data["video_url"] = None

    return data


@router.get("/clips/{id}/words")
def get_clip_words(
    id: str,
    start: Optional[float] = None,
    end: Optional[float] = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Point 2 : Renvoie les mots avec start, end, text, prob pour l'intervalle donné ou du clip."""
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    pdir = settings.data_dir / "projects" / clip.project_id
    s = start if start is not None else clip.start
    e = end if end is not None else clip.end
    return resolve_clip_words(pdir, clip.index, s, e)


@router.patch("/clips/{id}")
def update_clip(
    id: str,
    update: ClipUpdate,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Modifie le titre, début/fin ou les mots (start, end, text, prob)."""
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    if update.title is not None:
        clip.title = update.title
    if update.start is not None:
        clip.start = update.start
    if update.end is not None:
        clip.end = update.end

    pdir = settings.data_dir / "projects" / clip.project_id

    if update.words is not None:
        formatted_words = [
            {
                "start": float(w["start"]),
                "end": float(w["end"]),
                "text": str(w.get("text") or w.get("word") or "").strip(),
                "prob": float(w.get("prob") or w.get("score") or 1.0),
            }
            for w in update.words
            if str(w.get("text") or w.get("word") or "").strip()
        ]
        clean_words = deduplicate_words(formatted_words)
        custom_words_path = pdir / f"clip_{clip.index}_words.json"
        custom_words_path.write_text(json.dumps(clean_words, ensure_ascii=False, indent=2), encoding="utf-8")
    elif update.start is not None or update.end is not None:
        # L'intervalle a changé : si des mots custom existaient, on resynchronise la plage
        custom_words_path = pdir / f"clip_{clip.index}_words.json"
        if custom_words_path.exists():
            merged_words = resolve_clip_words(pdir, clip.index, clip.start, clip.end)
            custom_words_path.write_text(json.dumps(merged_words, ensure_ascii=False, indent=2), encoding="utf-8")

    session.add(clip)
    session.commit()
    session.refresh(clip)
    return clip.model_dump()


@router.post("/clips/{id}/words/regenerate")
def regenerate_subtitles(
    id: str,
    mode: str = "reset",
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """
    Regénère proprement les sous-titres du clip.
    - mode="reset" : réinitialise à partir de words.json du projet en nettoyant toute duplication.
    - mode="whisper" : exécute Whisper sur le segment audio spécifique [start, end].
    """
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    pdir = settings.data_dir / "projects" / clip.project_id
    new_words = regenerate_clip_words(pdir, clip.index, clip.start, clip.end, mode=mode)
    return new_words


@router.post("/clips/{id}/render", status_code=status.HTTP_202_ACCEPTED)
async def rerender_clip(
    id: str,
    req: ClipRenderRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Re-rendu ciblé d'un seul clip sans impacter le statut global du projet."""
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    clip.status = "rendering"
    session.add(clip)
    session.commit()

    try:
        await rerender_project_task.defer_async(
            project_id=clip.project_id,
            clip_id=id,
            layout=req.layout,
            fmt=req.format,
            cam=req.cam,
            captions=req.captions,
        )
    except Exception as exc:
        clip.status = "failed"
        session.add(clip)
        session.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "queued",
        "message": f"Job de re-rendu du clip #{clip.index} soumis au worker GPU",
        "clip_id": id,
    }


@router.post("/projects/{id}/render", status_code=status.HTTP_202_ACCEPTED)
async def rerender(
    id: str,
    req: ProjectRenderRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Re-rendu asynchrone via job Procrastinate (queue gpu)."""
    project = session.get(Project, id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    if req.clip_id:
        # Re-rendu ciblé d'un seul clip : seul le clip passe en status 'rendering'
        clip = session.get(Clip, req.clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip introuvable")
        clip.status = "rendering"
        session.add(clip)
        session.commit()
    else:
        # Re-rendu global du projet complet
        project.status = "rendering"
        project.step = "render"
        session.add(project)
        clips = session.exec(select(Clip).where(Clip.project_id == id)).all()
        for c in clips:
            c.status = "rendering"
            session.add(c)
        session.commit()

    try:
        await rerender_project_task.defer_async(
            project_id=id,
            clip_id=req.clip_id,
            layout=req.layout,
            fmt=req.format,
            cam=req.cam,
            captions=req.captions,
        )
    except Exception as exc:
        if req.clip_id:
            clip = session.get(Clip, req.clip_id)
            if clip:
                clip.status = "failed"
                session.add(clip)
                session.commit()
        else:
            project.status = "failed"
            project.error = f"Échec de mise en file du re-rendu: {exc}"
            session.add(project)
            session.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "queued",
        "message": f"Job de re-rendu {'du clip ' + req.clip_id if req.clip_id else 'du projet'} soumis au worker GPU",
        "project_id": id,
        "clip_id": req.clip_id,
    }
