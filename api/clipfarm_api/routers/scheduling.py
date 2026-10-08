from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Account, Clip, Project, Publication, PublicationOut
from ..publishing.base import PublicationPayload
from ..publishing.crypto import decrypt_tokens
from ..publishing.predictive_scheduler import PARIS_TZ, predict_schedule_with_gemini
from ..publishing.youtube import YouTubePublisher

router = APIRouter(prefix="", tags=["scheduling"])


class PredictScheduleRequest(BaseModel):
    project_id: Optional[str] = None
    clip_ids: Optional[list[str]] = None
    platforms: list[str] = Field(default_factory=lambda: ["youtube"])
    start_date: Optional[datetime] = None
    days_ahead: int = 7


class ScheduleItem(BaseModel):
    clip_id: str
    account_id: Optional[str] = None
    platform: str = "youtube"
    scheduled_at: datetime
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    privacy: str = "private"
    rights_confirmed: bool = False
    predictive_score: Optional[int] = None
    algorithmic_reason: Optional[str] = None


class ApplyScheduleRequest(BaseModel):
    items: list[ScheduleItem]


class RescheduleRequest(BaseModel):
    scheduled_at: datetime


@router.get("/scheduling/unscheduled-clips")
def list_unscheduled_clips(
    project_id: Optional[str] = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Retourne la liste des clips prêts qui ne sont pas encore programmés ou publiés."""
    # Récupérer les ID des clips déjà actifs dans une publication
    active_pubs = session.exec(
        select(Publication.clip_id).where(Publication.status.in_(["scheduled", "uploading", "published"]))
    ).all()
    scheduled_clip_ids = set(active_pubs)

    # Récupérer les clips prêts
    query = select(Clip).where(Clip.status == "ready")
    if project_id:
        query = query.where(Clip.project_id == project_id)

    clips = session.exec(query.order_by(Clip.created_at.desc())).all()

    results = []
    for c in clips:
        if c.id in scheduled_clip_ids:
            continue

        proj = session.get(Project, c.project_id)
        proj_title = "Projet"
        if proj:
            if proj.source_path:
                proj_title = Path(proj.source_path).stem
            elif proj.source_url:
                proj_title = proj.source_url
            else:
                proj_title = f"Projet #{proj.id[:6]}"

        duration = round(c.end - c.start, 1) if c.end and c.start else 0.0
        results.append({
            "id": c.id,
            "index": c.index,
            "project_id": c.project_id,
            "project_title": proj_title,
            "title": c.title,
            "hook": c.hook,
            "duration": duration,
            "start": c.start,
            "end": c.end,
            "scores": c.scores or {},
            "file_path": c.file_path,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return results


@router.get("/calendar/events")
def get_calendar_events(
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Retourne tous les événements du calendrier de publication avec métadonnées enrichies."""
    pubs = session.exec(select(Publication).order_by(Publication.scheduled_at.asc())).all()

    events = []
    for p in pubs:
        clip = session.get(Clip, p.clip_id)
        account = session.get(Account, p.account_id)
        proj = session.get(Project, clip.project_id) if clip else None
        proj_title = None
        if proj:
            if proj.source_path:
                proj_title = Path(proj.source_path).stem
            elif proj.source_url:
                proj_title = proj.source_url
            else:
                proj_title = f"Projet #{proj.id[:6]}"

        events.append({
            "id": p.id,
            "clip_id": p.clip_id,
            "project_id": clip.project_id if clip else None,
            "project_title": proj_title,
            "clip_title": clip.title if clip else None,
            "clip_hook": clip.hook if clip else None,
            "clip_duration": round(clip.end - clip.start, 1) if clip and clip.end and clip.start else 0,
            "platform": p.platform,
            "account_id": p.account_id,
            "account_name": account.name if account else "Compte",
            "account_avatar": account.avatar_url if account else None,
            "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "status": p.status,
            "url": p.url,
            "external_id": p.external_id,
            "error": p.error,
            "metadata": p.metadata_json or {},
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return events


@router.post("/scheduling/predict")
def generate_predictive_schedule(
    req: PredictScheduleRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """
    Sollicite l'IA Google Gemini pour concevoir une planification prédictive optimale
    des clips en fonction des créneaux de forte audience et des règles algorithmiques.
    """
    # 1. Récupérer les clips ciblés
    if req.clip_ids:
        clips = session.exec(select(Clip).where(Clip.id.in_(req.clip_ids))).all()
    else:
        # Tous les clips prêts non encore programmés
        active_pubs = session.exec(
            select(Publication.clip_id).where(Publication.status.in_(["scheduled", "uploading", "published"]))
        ).all()
        sched_ids = set(active_pubs)
        query = select(Clip).where(Clip.status == "ready")
        if req.project_id:
            query = query.where(Clip.project_id == req.project_id)
        clips = [c for c in session.exec(query).all() if c.id not in sched_ids]

    if not clips:
        return {"predictions": [], "summary": "Aucun clip à planifier."}

    # 2. Récupérer la transcription contextuelle de chaque clip
    clips_data = []
    for c in clips:
        transcript = ""
        pdir = settings.data_dir / "projects" / c.project_id
        custom_words = pdir / f"clip_{c.index}_words.json"
        if custom_words.is_file():
            try:
                words = json.loads(custom_words.read_text(encoding="utf-8"))
                transcript = " ".join(str(w.get("text") or w.get("word") or "") for w in words)
            except Exception:
                pass
        if not transcript:
            master_words = pdir / "words.json"
            if master_words.is_file():
                try:
                    words = json.loads(master_words.read_text(encoding="utf-8"))
                    transcript = " ".join(
                        str(w.get("text") or w.get("word") or "")
                        for w in words
                        if float(w.get("start", 0)) >= c.start and float(w.get("end", 0)) <= c.end
                    )
                except Exception:
                    pass

        clips_data.append({
            "id": c.id,
            "index": c.index,
            "title": c.title,
            "hook": c.hook,
            "reason": c.reason,
            "start": c.start,
            "end": c.end,
            "scores": c.scores or {},
            "transcript": transcript,
        })

    # 3. Récupérer les publications déjà programmées pour le contexte de non-collision
    existing_pubs = session.exec(
        select(Publication).where(Publication.status.in_(["scheduled", "published"]))
    ).all()
    existing_data = [
        {
            "platform": p.platform,
            "scheduled_at": p.scheduled_at,
            "metadata_json": p.metadata_json,
        }
        for p in existing_pubs
    ]

    return predict_schedule_with_gemini(
        clips=clips_data,
        existing_publications=existing_data,
        target_platforms=req.platforms,
        start_date=req.start_date,
        days_ahead=req.days_ahead,
    )


@router.post("/scheduling/apply")
async def apply_schedule(
    req: ApplyScheduleRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Applique et enregistre les créneaux planifiés après confirmation des droits."""
    if not req.items:
        raise HTTPException(status_code=400, detail="Aucun élément à planifier.")

    created_pubs = []
    for item in req.items:
        if not item.rights_confirmed:
            raise HTTPException(
                status_code=400,
                detail=f"Vous devez confirmer détenir les droits pour programmer le clip '{item.title}'.",
            )

        clip = session.get(Clip, item.clip_id)
        if not clip:
            continue

        target_acc_id = item.account_id
        if not target_acc_id:
            acc = session.exec(select(Account).where(Account.platform == item.platform)).first()
            if not acc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Aucun compte connecté pour la plateforme {item.platform}.",
                )
            target_acc_id = acc.id

        raw_key = f"{clip.id}_{target_acc_id}_{item.title}_{item.scheduled_at.isoformat()}"
        idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

        pub_id = f"pub_{uuid.uuid4().hex[:10]}"
        metadata = {
            "title": item.title,
            "description": item.description,
            "tags": item.tags,
            "privacy": item.privacy,
            "predictive_score": item.predictive_score,
            "algorithmic_reason": item.algorithmic_reason,
        }

        pub = Publication(
            id=pub_id,
            clip_id=clip.id,
            account_id=target_acc_id,
            platform=item.platform,
            metadata_json=metadata,
            scheduled_at=item.scheduled_at,
            status="scheduled",
            idempotency_key=idempotency_key,
            rights_confirmed=True,
        )
        session.add(pub)
        created_pubs.append(pub_id)

    session.commit()
    return {"ok": True, "count": len(created_pubs), "publication_ids": created_pubs}


@router.patch("/publications/{id}/reschedule")
def reschedule_publication(
    id: str,
    req: RescheduleRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Met à jour la date et l'heure de publication d'un clip planifié."""
    pub = session.get(Publication, id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication introuvable")

    if pub.status == "published":
        raise HTTPException(status_code=400, detail="Impossible de replanifier un clip déjà publié.")

    pub.scheduled_at = req.scheduled_at
    pub.status = "scheduled"
    session.add(pub)
    session.commit()

    return {
        "ok": True,
        "id": pub.id,
        "scheduled_at": pub.scheduled_at.isoformat(),
        "status": pub.status,
    }


@router.post("/publications/{id}/publish-now")
async def publish_scheduled_now(
    id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Force la publication immédiate d'un clip préalablement planifié."""
    pub = session.get(Publication, id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication introuvable")

    if pub.status == "published":
        return {"ok": True, "status": "already_published", "url": pub.url}

    clip = session.get(Clip, pub.clip_id)
    account = session.get(Account, pub.account_id)
    if not clip or not account:
        raise HTTPException(status_code=400, detail="Clip ou compte associé introuvable")

    if not clip.file_path or not Path(clip.file_path).is_file():
        raise HTTPException(status_code=400, detail="Fichier vidéo manquant sur le disque")

    tokens = decrypt_tokens(account.encrypted_tokens)
    if not tokens:
        raise HTTPException(status_code=401, detail="Jetons de compte invalides")

    if pub.platform != "youtube":
        raise HTTPException(status_code=400, detail=f"Plateforme '{pub.platform}' non supportée pour l'envoi direct.")

    publisher = YouTubePublisher()
    video_path = Path(clip.file_path)
    meta = pub.metadata_json or {}

    payload = PublicationPayload(
        title=meta.get("title") or clip.title,
        description=meta.get("description", ""),
        tags=meta.get("tags", []),
        privacy=meta.get("privacy", "public"),
        made_for_kids=meta.get("made_for_kids", False),
        category_id=meta.get("category_id", "22"),
        scheduled_at=None,  # Immédiat
    )

    pub.status = "uploading"
    session.add(pub)
    session.commit()

    try:
        res = await publisher.upload(tokens, payload, video_path)
        if res.success:
            pub.status = "published"
            pub.external_id = res.external_id
            pub.url = res.url
            pub.published_at = datetime.now(timezone.utc)
            pub.error = None
        else:
            pub.status = "failed"
            pub.error = res.error
    except Exception as exc:
        pub.status = "failed"
        pub.error = str(exc)

    session.add(pub)
    session.commit()

    return {
        "ok": pub.status == "published",
        "status": pub.status,
        "url": pub.url,
        "error": pub.error,
    }


@router.post("/clips/{id}/predict-slots")
def predict_best_slots_for_clip(
    id: str,
    platform: str = "youtube",
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Suggère les 3 meilleurs créneaux prédictifs avec IA pour un clip individuel."""
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    pdir = settings.data_dir / "projects" / clip.project_id
    transcript = ""
    words_file = pdir / f"clip_{clip.index}_words.json"
    if words_file.is_file():
        try:
            words = json.loads(words_file.read_text(encoding="utf-8"))
            transcript = " ".join(str(w.get("text") or w.get("word") or "") for w in words)
        except Exception:
            pass

    # Récupérer les publications existantes
    existing_pubs = session.exec(
        select(Publication).where(Publication.status.in_(["scheduled", "published"]))
    ).all()
    existing_data = [
        {"platform": p.platform, "scheduled_at": p.scheduled_at, "metadata_json": p.metadata_json}
        for p in existing_pubs
    ]

    clip_dict = {
        "id": clip.id,
        "index": clip.index,
        "title": clip.title,
        "hook": clip.hook,
        "reason": clip.reason,
        "start": clip.start,
        "end": clip.end,
        "scores": clip.scores or {},
        "transcript": transcript,
    }

    # Demander à Gemini / algorithme
    result = predict_schedule_with_gemini(
        clips=[clip_dict],
        existing_publications=existing_data,
        target_platforms=[platform],
        days_ahead=7,
    )

    return result

