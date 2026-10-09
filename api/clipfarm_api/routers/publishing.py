from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Account, Clip, Project, Publication, PublicationCreate, PublicationOut
from ..publishing.base import PublicationPayload
from ..publishing.crypto import decrypt_tokens
from ..publishing.metadata import generate_publishing_metadata
from ..publishing.youtube import YouTubePublisher

router = APIRouter(tags=["publishing"])


class GenerateMetadataRequest(BaseModel):
    platform: str = "youtube"


@router.post("/clips/{id}/metadata")
def get_clip_metadata(
    id: str,
    req: GenerateMetadataRequest = GenerateMetadataRequest(),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Génère des métadonnées (titre, description, hashtags) optimisées pour la plateforme ciblée."""
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    pdir = settings.data_dir / "projects" / clip.project_id
    transcript = ""

    # Extraire les mots de la transcription pour le contexte LLM
    custom_words_path = pdir / f"clip_{clip.index}_words.json"
    if custom_words_path.exists():
        try:
            words = json.loads(custom_words_path.read_text(encoding="utf-8"))
            transcript = " ".join(str(w.get("text") or w.get("word") or "") for w in words)
        except Exception:
            pass

    if not transcript:
        words_path = pdir / "words.json"
        if words_path.exists():
            try:
                words = json.loads(words_path.read_text(encoding="utf-8"))
                transcript = " ".join(
                    str(w.get("text") or w.get("word") or "")
                    for w in words
                    if float(w.get("start", 0)) >= clip.start and float(w.get("end", 0)) <= clip.end
                )
            except Exception:
                pass

    # Récupérer les métadonnées vérifiées de la vidéo source (chaîne, titre original, description)
    creator_name = ""
    source_title = ""
    source_desc = ""

    meta_file = pdir / "metadata.json"
    if meta_file.exists():
        try:
            m = json.loads(meta_file.read_text(encoding="utf-8"))
            creator_name = m.get("uploader") or m.get("channel") or ""
            source_title = m.get("title") or ""
            source_desc = m.get("description") or ""
        except Exception:
            pass

    if not creator_name or not source_title:
        info_file = pdir / "source.info.json"
        if info_file.exists():
            try:
                inf = json.loads(info_file.read_text(encoding="utf-8"))
                if not creator_name:
                    creator_name = inf.get("uploader") or inf.get("channel") or ""
                if not source_title:
                    source_title = inf.get("title") or inf.get("fulltitle") or ""
                if not source_desc:
                    source_desc = inf.get("description") or ""
            except Exception:
                pass

    if not source_title:
        proj = session.get(Project, clip.project_id)
        if proj:
            if proj.source_path:
                source_title = Path(proj.source_path).stem
            elif proj.source_url:
                source_title = proj.source_url

    # Extraire plusieurs images représentatives pour analyse visuelle multi-angles par IA
    image_paths: list[Path] = []
    frame_dir = pdir / "preview_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    import subprocess

    # 1. Images grand-angle de la vidéo source (capture les personnes, la facecam, le décor réel)
    source_mp4 = pdir / "source.mp4"
    if not source_mp4.exists():
        proj = session.get(Project, clip.project_id)
        if proj and proj.source_path and Path(proj.source_path).is_file():
            source_mp4 = Path(proj.source_path)

    if source_mp4.exists() and clip.start is not None and clip.end is not None:
        duration = max(1.0, clip.end - clip.start)
        # Échantillonner 3 moments clés : début (20%), milieu (50%), fin (80%)
        sample_times = [
            clip.start + duration * 0.2,
            clip.start + duration * 0.5,
            clip.start + duration * 0.8,
        ]
        for idx, t in enumerate(sample_times, start=1):
            source_frame = frame_dir / f"clip_{clip.index}_source_{idx}.jpg"
            if not source_frame.exists() or source_frame.stat().st_size == 0:
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(source_mp4), "-frames:v", "1", "-q:v", "2", str(source_frame)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                except Exception:
                    pass
            if source_frame.exists() and source_frame.stat().st_size > 0:
                image_paths.append(source_frame)

    # 2. Image du clip vertical rendu (capture le cadrage vertical et l'incrustation)
    if clip.file_path and Path(clip.file_path).is_file():
        vid_p = Path(clip.file_path)
        clip_frame = frame_dir / f"clip_{clip.index}_vertical.jpg"
        if not clip_frame.exists() or clip_frame.stat().st_size == 0:
            try:
                mid_s = max(0.5, (clip.end - clip.start) * 0.4) if clip.end and clip.start else 1.0
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", f"{mid_s:.2f}", "-i", str(vid_p), "-frames:v", "1", "-q:v", "2", str(clip_frame)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            except Exception:
                pass
        if clip_frame.exists() and clip_frame.stat().st_size > 0:
            image_paths.append(clip_frame)

    return generate_publishing_metadata(
        clip_title=clip.title,
        hook=clip.hook,
        transcript=transcript,
        platform=req.platform,
        image_paths=image_paths,
        creator_name=creator_name,
        source_title=source_title,
        source_description=source_desc,
        reason=clip.reason,
        scores=clip.scores,
    )


@router.post("/clips/{id}/validate-publish")
def validate_publication_payload(
    id: str,
    req: PublicationCreate,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Valide les limites et exigences de la plateforme avant publication."""
    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    video_path = Path(clip.file_path) if clip.file_path else None
    payload = PublicationPayload(
        title=req.title,
        description=req.description,
        tags=req.tags,
        privacy=req.privacy,
        made_for_kids=req.made_for_kids,
        category_id=req.category_id,
        scheduled_at=req.scheduled_at,
    )

    if req.platform == "youtube":
        publisher = YouTubePublisher()
        res = publisher.validate(payload, video_path)
        return {
            "valid": res.valid,
            "errors": res.errors,
            "warnings": res.warnings,
        }
    elif req.platform in ("tiktok", "postiz", "instagram"):
        from ..publishing.postiz import PostizPublisher
        publisher = PostizPublisher()
        res = publisher.validate(payload, video_path)
        return {
            "valid": res.valid,
            "errors": res.errors,
            "warnings": res.warnings,
        }

    return {"valid": True, "errors": [], "warnings": []}


@router.post("/clips/{id}/publish", response_model=PublicationOut, status_code=status.HTTP_201_CREATED)
async def publish_clip(
    id: str,
    req: PublicationCreate,
    session: Session = Depends(get_session),
) -> PublicationOut:
    """Publie un clip sur la plateforme sélectionnée après validation explicite des droits."""
    # Règle non négociable : confirmation explicite des droits
    if not req.rights_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Vous devez certifier détenir les droits d'exploitation et de diffusion sur ce contenu avant de publier.",
        )

    clip = session.get(Clip, id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip introuvable")

    if not clip.file_path or not Path(clip.file_path).is_file():
        raise HTTPException(status_code=400, detail="Fichier vidéo du clip introuvable sur le disque.")

    target_account_id = req.account_id
    if not target_account_id:
        acc = session.exec(select(Account).where(Account.platform == req.platform)).first()
        if not acc:
            raise HTTPException(
                status_code=400,
                detail=f"Aucun compte connecté trouvé pour la plateforme {req.platform}. Rendez-vous dans 'Comptes' pour en connecter un.",
            )
        account = acc
    else:
        account = session.get(Account, target_account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Compte de publication introuvable")

    if account.platform != req.platform:
        raise HTTPException(status_code=400, detail="La plateforme du compte ne correspond pas à la cible.")

    # Déchiffrer les jetons du compte
    tokens = decrypt_tokens(account.encrypted_tokens)
    if not tokens:
        raise HTTPException(status_code=401, detail="Jetons d'authentification invalides ou corrompus.")

    video_path = Path(clip.file_path)
    payload = PublicationPayload(
        title=req.title,
        description=req.description,
        tags=req.tags,
        privacy=req.privacy,
        made_for_kids=req.made_for_kids,
        category_id=req.category_id,
        scheduled_at=req.scheduled_at,
    )

    # Clé d'idempotence unique
    raw_key = f"{id}_{account.id}_{req.title}_{req.scheduled_at}"
    idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

    # Vérifier l'adaptateur
    if req.platform == "youtube":
        publisher = YouTubePublisher()
    elif req.platform in ("tiktok", "postiz", "instagram"):
        from ..publishing.postiz import PostizPublisher
        publisher = PostizPublisher()
    else:
        raise HTTPException(status_code=400, detail=f"Plateforme '{req.platform}' non encore supportée.")

    validation = publisher.validate(payload, video_path)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=" ; ".join(validation.errors))

    pub_id = f"pub_{uuid.uuid4().hex[:10]}"
    metadata_dict = {
        "title": req.title,
        "description": req.description,
        "tags": req.tags,
        "privacy": req.privacy,
        "made_for_kids": req.made_for_kids,
        "category_id": req.category_id,
        "predictive_score": req.predictive_score,
        "algorithmic_reason": req.algorithmic_reason,
    }

    pub = Publication(
        id=pub_id,
        clip_id=clip.id,
        account_id=account.id,
        platform=req.platform,
        metadata_json=metadata_dict,
        scheduled_at=req.scheduled_at,
        status="uploading" if req.publish_now else "scheduled",
        idempotency_key=idempotency_key,
        rights_confirmed=True,
    )
    session.add(pub)
    session.commit()
    session.refresh(pub)

    # Si publication immédiate
    if req.publish_now:
        try:
            upload_res = await publisher.upload(tokens, payload, video_path)
            if upload_res.success:
                pub.status = "published"
                pub.external_id = upload_res.external_id
                pub.url = upload_res.url
                pub.published_at = datetime.now(timezone.utc)
                pub.error = None
            else:
                pub.status = "failed"
                pub.error = upload_res.error or "Échec inconnu lors de l'envoi"
        except Exception as exc:
            pub.status = "failed"
            pub.error = str(exc)

        session.add(pub)
        session.commit()
        session.refresh(pub)
    else:
        # Enregistrement de la tâche différée dans la file Procrastinate
        try:
            from ..queue import execute_scheduled_publication
            await execute_scheduled_publication.configure(
                lock=f"pub_{pub.id}",
                schedule_at=pub.scheduled_at,
            ).defer_async(publication_id=pub.id)
        except Exception as exc:
            import logging
            logging.getLogger("clipfarm_api").warning("Impossible d'enfiler la tâche différée Procrastinate: %s", exc)

    return PublicationOut(
        id=pub.id,
        clip_id=pub.clip_id,
        account_id=pub.account_id,
        platform=pub.platform,
        metadata_json=pub.metadata_json,
        scheduled_at=pub.scheduled_at,
        status=pub.status,
        external_id=pub.external_id,
        url=pub.url,
        error=pub.error,
        rights_confirmed=pub.rights_confirmed,
        created_at=pub.created_at,
        published_at=pub.published_at,
    )


@router.get("/publications", response_model=list[PublicationOut])
def list_publications(session: Session = Depends(get_session)) -> list[PublicationOut]:
    """Liste de toutes les publications avec leur statut."""
    pubs = session.exec(select(Publication).order_by(Publication.created_at.desc())).all()
    return [
        PublicationOut(
            id=p.id,
            clip_id=p.clip_id,
            account_id=p.account_id,
            platform=p.platform,
            metadata_json=p.metadata_json,
            scheduled_at=p.scheduled_at,
            status=p.status,
            external_id=p.external_id,
            url=p.url,
            error=p.error,
            rights_confirmed=p.rights_confirmed,
            created_at=p.created_at,
            published_at=p.published_at,
        )
        for p in pubs
    ]


@router.get("/publications/{id}", response_model=PublicationOut)
def get_publication(id: str, session: Session = Depends(get_session)) -> PublicationOut:
    """Détail d'une publication."""
    pub = session.get(Publication, id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication introuvable")
    return PublicationOut(
        id=pub.id,
        clip_id=pub.clip_id,
        account_id=pub.account_id,
        platform=pub.platform,
        metadata_json=pub.metadata_json,
        scheduled_at=pub.scheduled_at,
        status=pub.status,
        external_id=pub.external_id,
        url=pub.url,
        error=pub.error,
        rights_confirmed=pub.rights_confirmed,
        created_at=pub.created_at,
        published_at=pub.published_at,
    )


@router.delete("/publications/{id}")
def delete_publication(id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Supprime une publication de la base."""
    pub = session.get(Publication, id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication introuvable")
    session.delete(pub)
    try:
        from sqlmodel import text
        session.exec(
            text(
                "DELETE FROM procrastinate_jobs WHERE queue_name = 'publish' "
                "AND args->>'publication_id' = :pub_id AND status = 'todo'"
            ),
            params={"pub_id": id},
        )
    except Exception:
        pass
    session.commit()
    return {"ok": True, "id": id, "message": "Publication supprimée"}
