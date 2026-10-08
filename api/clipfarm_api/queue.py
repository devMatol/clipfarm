from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
import procrastinate
from sqlmodel import Session, select

from .config import settings
from .db import engine
from .models import Clip, Project


import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_procrastinate_app() -> procrastinate.App:
    # Postgres obligatoire (aucun repli SQLite ni InMemory)
    connector = procrastinate.PsycopgConnector(conninfo=settings.database_url)
    return procrastinate.App(connector=connector)


procrastinate_app = get_procrastinate_app()


def _update_project_progress(project_id: str, step: str, pct: float, msg: str, status: str = "running") -> None:
    with Session(engine) as session:
        proj = session.get(Project, project_id)
        if proj:
            proj.step = step
            proj.progress = pct
            proj.status = status
            session.add(proj)
            session.commit()


@procrastinate_app.task(queue="gpu")
def process_project(project_id: str) -> None:
    from clipfarm_engine import pipeline
    from clipfarm_engine.config import Settings as EngineSettings
    from clipfarm_engine.media.layouts import Rect

    with Session(engine) as session:
        project = session.get(Project, project_id)
        if not project:
            return
        source = project.source_path or project.source_url
        if not source:
            project.status = "failed"
            project.error = "Aucune source spécifiée"
            session.add(project)
            session.commit()
            return

        project.status = "ingesting"
        project.error = None
        session.add(project)
        session.commit()
        custom_settings = project.settings_json or {}

    def progress_callback(step: str, pct: float, msg: str) -> None:
        status_map = {
            "ingest": "ingesting",
            "audio": "transcribing",
            "voice": "transcribing",
            "transcribe": "transcribing",
            "signals": "analysing",
            "highlights": "detecting",
            "render": "rendering",
            "done": "ready",
        }
        current_status = status_map.get(step, "running")
        _update_project_progress(project_id, step, pct, msg, status=current_status)

    try:
        engine_settings = EngineSettings()
        if custom_settings.get("max_clips") is not None:
            engine_settings.max_clips = int(custom_settings["max_clips"])
        if custom_settings.get("min_clip_s") is not None:
            engine_settings.min_clip_s = float(custom_settings["min_clip_s"])
        if custom_settings.get("max_clip_s") is not None:
            engine_settings.max_clip_s = float(custom_settings["max_clip_s"])
        if custom_settings.get("llm"):
            engine_settings.llm_provider = str(custom_settings["llm"])

        # Ingestion préalable
        p = pipeline.ingest(source, engine_settings, progress_callback)

        layout_choice = custom_settings.get("layout", "center")
        cam_data = custom_settings.get("cam")

        # Point 4 : Si URL + layout facecam et pas encore de cam définie -> mise en attente awaiting_cam
        if project.source_url and layout_choice in ("facecam_top", "facecam_bottom") and not cam_data:
            from clipfarm_engine.media import ffmpeg
            frame_path = p.dir / "frame_5.jpg"
            if not frame_path.exists():
                import subprocess
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", "5", "-i", str(p.source), "-frames:v", "1", "-q:v", "2", str(frame_path)],
                    check=False,
                )
            with Session(engine) as session:
                proj = session.get(Project, project_id)
                if proj:
                    proj.status = "awaiting_cam"
                    proj.step = "awaiting_cam"
                    proj.progress = 0.15
                    session.add(proj)
                    session.commit()
            return  # Le job attend que l'utilisateur valide la cam via /projects/{id}/set-cam

        cam_rect = None
        if cam_data:
            cam_rect = Rect(
                x=float(cam_data.get("x", 0.7)),
                y=float(cam_data.get("y", 0.08)),
                w=float(cam_data.get("w", 0.25)),
                h=float(cam_data.get("h", 0.25)),
            )

        skip_subs = bool(custom_settings.get("skip_if_subtitles_present", True))
        render_opts = pipeline.RenderOptions(
            layout=layout_choice,
            fmt=custom_settings.get("format", "9:16"),
            captions=custom_settings.get("captions", "punchy"),
            cam=cam_rect,
            skip_if_subtitles_present=skip_subs,
        )

        # Analyse + Détection + Rendu
        words, signals = pipeline.analyse(p, engine_settings, transcribe=custom_settings.get("transcribe", True), progress=progress_callback)
        cands = pipeline.detect(p, words, signals, engine_settings, progress=progress_callback)
        clips_rendered = pipeline.render_all(p, cands, words, render_opts, progress=progress_callback)

        # Enregistrement en base
        ai_count = 0
        with Session(engine) as session:
            db_project = session.get(Project, project_id)
            if db_project:
                existing_clips = session.exec(select(Clip).where(Clip.project_id == project_id)).all()
                for c in existing_clips:
                    session.delete(c)

                for item in clips_rendered:
                    actual_layout = item.get("layout", render_opts.layout)
                    is_ai = item.get("reason") != "signal audio/scene"
                    if is_ai:
                        ai_count += 1
                    clip_origin = "IA" if is_ai else "Repli son/image"

                    clip_record = Clip(
                        id=f"{project_id}_{item['index']}",
                        project_id=project_id,
                        index=item["index"],
                        start=item["start"],
                        end=item["end"],
                        title=item.get("title", f"Clip {item['index']}"),
                        hook=item.get("hook", ""),
                        reason=item.get("reason", ""),
                        scores={
                            **(item.get("scores") or {}),
                            "origin": clip_origin,
                        },
                        final_score=float(item.get("final_score", 0.0)),
                        layout={
                            "name": actual_layout,
                            "fmt": render_opts.fmt,
                            "cam": (cam_data or {"x": render_opts.cam.x, "y": render_opts.cam.y, "w": render_opts.cam.w, "h": render_opts.cam.h}) if (render_opts.cam and actual_layout != "center") else None,
                            "face_fallback": bool(item.get("face_fallback", False)),
                            "burned_subtitles_detected": bool(item.get("burned_subtitles_detected", False)),
                            "origin": clip_origin,
                        },
                        captions={"preset": render_opts.captions},
                        file_path=item.get("file", ""),
                        status="ready",
                    )
                    session.add(clip_record)

                proj_settings = db_project.settings_json or {}
                proj_settings["ai_clips_count"] = ai_count
                if ai_count == 0:
                    proj_settings["ai_fallback_reason"] = (
                        "Aucun moment fort n'a été retenu par le modèle IA ou le LLM était indisponible. "
                        "Les clips ont été générés par repli automatique sur les signaux physiques (pics sonores & changements de plan)."
                    )
                db_project.settings_json = proj_settings
                db_project.status = "ready"
                db_project.step = "done"
                db_project.progress = 1.0
                session.add(db_project)
                session.commit()

        _update_project_progress(project_id, "done", 1.0, f"{len(clips_rendered)} clips prêts", status="ready")

    except Exception as exc:
        with Session(engine) as session:
            db_project = session.get(Project, project_id)
            if db_project:
                db_project.status = "failed"
                db_project.error = str(exc)
                session.add(db_project)
                session.commit()
        raise


@procrastinate_app.task(queue="gpu")
def rerender_project_task(
    project_id: str,
    clip_id: Optional[str] = None,
    layout: Optional[str] = None,
    fmt: Optional[str] = None,
    cam: Optional[dict[str, float]] = None,
    captions: Optional[str] = None,
) -> None:
    """Job de re-rendu exécuté de manière asynchrone par le worker GPU."""
    from clipfarm_engine.captions.ass import PRESETS, Word, build_ass
    from clipfarm_engine.media import ffmpeg, layouts, render
    from .words import resolve_clip_words

    if not clip_id:
        _update_project_progress(project_id, "render", 0.7, "Re-rendu en cours...", status="rendering")

    try:
        with Session(engine) as session:
            project = session.get(Project, project_id)
            if not project:
                return

            pdir = settings.data_dir / "projects" / project_id

            # Retrouver la source
            source_file = None
            if project.source_path and Path(project.source_path).is_file():
                source_file = Path(project.source_path)
            elif (pdir / "source.mp4").is_file():
                source_file = pdir / "source.mp4"
            elif (pdir / "source.json").is_file():
                src_info = json.loads((pdir / "source.json").read_text(encoding="utf-8"))
                source_file = Path(src_info["path"])

            if not source_file or not source_file.exists():
                raise FileNotFoundError(f"Source introuvable pour {project_id}")

            if clip_id:
                clips_to_render = [session.get(Clip, clip_id)]
            else:
                clips_to_render = session.exec(select(Clip).where(Clip.project_id == project_id)).all()

            cdir = pdir / "clips"
            cdir.mkdir(exist_ok=True)

            for c in clips_to_render:
                if not c:
                    continue
                c.status = "rendering"
                session.add(c)
                session.commit()

                layout_name = layout or (c.layout.get("name") if c.layout else "center")
                fmt_name = fmt or (c.layout.get("fmt") if c.layout else "9:16")
                captions_preset = captions if captions is not None else (c.captions.get("preset") if c.captions else "punchy")

                # Réutiliser cam de clip.layout si non fourni
                cam_data = cam if cam is not None else (c.layout.get("cam") if c.layout else None)
                cam_rect = None
                if cam_data:
                    cam_rect = layouts.Rect(
                        x=float(cam_data.get("x", 0.7)),
                        y=float(cam_data.get("y", 0.08)),
                        w=float(cam_data.get("w", 0.25)),
                        h=float(cam_data.get("h", 0.25)),
                    )

                # Découpe frame-accurate
                raw_target = cdir / f"{c.index:02d}.raw.mp4"
                raw = ffmpeg.cut(source_file, raw_target, c.start, c.end)

                # Résolution intelligente des mots : inclut automatiquement toute portion de temps ajoutée
                resolved_words_data = resolve_clip_words(pdir, c.index, c.start, c.end)
                custom_words_path = pdir / f"clip_{c.index}_words.json"
                custom_words_path.write_text(json.dumps(resolved_words_data, ensure_ascii=False, indent=2), encoding="utf-8")

                clip_words = [
                    Word(
                        start=float(w["start"]),
                        end=float(w["end"]),
                        text=str(w.get("text") or w.get("word") or ""),
                        prob=float(w.get("prob") or w.get("score") or 1.0),
                    )
                    for w in resolved_words_data
                ]

                ass_path = None
                if captions_preset and clip_words:
                    ass_path = cdir / f"{c.index:02d}.ass"
                    ass_content = build_ass(clip_words, PRESETS[captions_preset], play_res=layouts.FORMATS[fmt_name], offset=c.start)
                    ass_path.write_text(ass_content, encoding="utf-8")

                # Si layout facecam sélectionné, vérifier la présence d'un visage sur 3 frames
                face_fallback = False
                actual_layout = layout_name
                if actual_layout in ("facecam_top", "facecam_bottom") and cam_rect:
                    from clipfarm_engine.media.face_detect import check_face_in_region
                    has_face = check_face_in_region(raw, cam_rect, num_samples=3)
                    if not has_face:
                        actual_layout = "center"
                        face_fallback = True

                final_target = cdir / f"{c.index:02d}.mp4"
                final = render.render_clip(raw, final_target, actual_layout, fmt_name, ass_path, cam_rect if actual_layout != "center" else None)

                c.file_path = str(final.resolve())
                c.layout = {
                    "name": actual_layout,
                    "fmt": fmt_name,
                    "cam": cam_data if actual_layout != "center" else None,
                    "face_fallback": face_fallback,
                }
                c.captions = {"preset": captions_preset}
                c.status = "ready"
                session.add(c)
                session.commit()

            if not clip_id:
                project.status = "ready"
                project.step = "done"
                project.progress = 1.0
                session.add(project)
                session.commit()
                _update_project_progress(project_id, "done", 1.0, "Re-rendu terminé", status="ready")

    except Exception as exc:
        with Session(engine) as session:
            if clip_id:
                failed_clip = session.get(Clip, clip_id)
                if failed_clip:
                    failed_clip.status = "failed"
                    session.add(failed_clip)
                    session.commit()
            else:
                p = session.get(Project, project_id)
                if p:
                    p.status = "failed"
                    p.error = str(exc)
                    session.add(p)
                    session.commit()
        raise


@procrastinate_app.task(queue="publish")
def execute_scheduled_publication(publication_id: str) -> None:
    """Tâche de publication asynchrone différée (exécutée à scheduled_at)."""
    import asyncio
    from datetime import datetime, timezone
    from pathlib import Path
    from .models import Account, Clip, Publication
    from .publishing.base import PublicationPayload
    from .publishing.crypto import decrypt_tokens
    from .publishing.youtube import YouTubePublisher

    with Session(engine) as session:
        pub = session.get(Publication, publication_id)
        if not pub or pub.status not in ("scheduled", "draft"):
            return

        if not pub.rights_confirmed:
            pub.status = "failed"
            pub.error = "Droits non confirmés"
            session.add(pub)
            session.commit()
            return

        clip = session.get(Clip, pub.clip_id)
        account = session.get(Account, pub.account_id)
        if not clip or not account:
            pub.status = "failed"
            pub.error = "Clip ou compte introuvable"
            session.add(pub)
            session.commit()
            return

        if not clip.file_path or not Path(clip.file_path).is_file():
            pub.status = "failed"
            pub.error = "Fichier vidéo manquant sur le disque"
            session.add(pub)
            session.commit()
            return

        tokens = decrypt_tokens(account.encrypted_tokens)
        if not tokens:
            pub.status = "failed"
            pub.error = "Jetons d'authentification invalides"
            session.add(pub)
            session.commit()
            return

        pub.status = "uploading"
        pub.attempts += 1
        session.add(pub)
        session.commit()

        video_path = Path(clip.file_path)
        meta = pub.metadata_json or {}
        payload = PublicationPayload(
            title=meta.get("title") or clip.title,
            description=meta.get("description", ""),
            tags=meta.get("tags", []),
            privacy=meta.get("privacy", "public"),
            made_for_kids=meta.get("made_for_kids", False),
            category_id=meta.get("category_id", "22"),
            scheduled_at=None,
        )

        try:
            if pub.platform == "youtube":
                publisher = YouTubePublisher()
                res = asyncio.run(publisher.upload(tokens, payload, video_path))
                if res.success:
                    pub.status = "published"
                    pub.external_id = res.external_id
                    pub.url = res.url
                    pub.published_at = datetime.now(timezone.utc)
                    pub.error = None
                else:
                    pub.status = "failed"
                    pub.error = res.error
            else:
                pub.status = "failed"
                pub.error = f"Plateforme {pub.platform} non supportée"
        except Exception as exc:
            pub.status = "failed"
            pub.error = str(exc)

        session.add(pub)
        session.commit()

