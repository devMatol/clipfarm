from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from sqlmodel import Session, select

from clipfarm_api.config import settings
from clipfarm_api.db import get_session
from clipfarm_api.main import app
from clipfarm_api.models import Project, Clip
from clipfarm_api.queue import procrastinate_app


@pytest.mark.gpu
@pytest.mark.asyncio
async def test_real_pipeline_e2e_gpu():
    """
    Test de bout en bout RÉEL (marqué gpu) :
    1. Vérifie la présence du fichier source réel de 25s
    2. Upload du fichier vers l'API
    3. Exécution du worker Procrastinate (qui appelle le pipeline complet : signaux, whisper/transcription, rendu)
    4. Attente du statut 'ready'
    5. Validation des clips produits et de leurs métadonnées
    """
    sample_path = Path("engine/tests/golden/gta6_sample_25s.mp4").resolve()
    assert sample_path.exists(), f"Sample source {sample_path} not found"

    # Restaurer le vrai engine Postgres et le vrai data_dir pour le test E2E réel
    from sqlmodel import create_engine
    import clipfarm_api.db as api_db
    import clipfarm_api.queue as api_queue

    real_engine = create_engine(settings.database_url, echo=False)
    api_db.engine = real_engine
    api_queue.engine = real_engine
    app.dependency_overrides.clear()
    settings.data_dir = Path("data").resolve()
    settings.upload_dir = settings.data_dir / "uploads"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # Vérification que le schéma Procrastinate est prêt
    try:
        with procrastinate_app.open():
            procrastinate_app.schema_manager.apply_schema()
    except Exception:
        pass

    # 1. Upload via l'API
    async with procrastinate_app.open_async():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            with open(sample_path, "rb") as f:
                files = {"file": ("gta6_sample_25s.mp4", f, "video/mp4")}
                data = {
                    "layout": "facecam_top",
                    "format": "9:16",
                    "cam": "0.739,0.083,0.246,0.245",
                    "captions": "punchy",
                    "max_clips": 1,
                }
                res = await ac.post("/projects/upload", files=files, data=data)
                assert res.status_code == 201, res.text
                project_data = res.json()["project"]
                proj_id = project_data["id"]

            print(f"\n[E2E] Projet créé : {proj_id}, status={project_data['status']}")

            # 2. Exécution du worker dans un thread pour traiter le job
            import threading
            def run_worker_thread():
                # concurrency=1, timeout pour le worker
                try:
                    procrastinate_app.run_worker(queues=["gpu"], concurrency=1, wait=0.5)
                except Exception as e:
                    print(f"[Worker Thread Error] {e}")

            worker_thread = threading.Thread(target=run_worker_thread, daemon=True)
            worker_thread.start()

            # 3. Polling de l'état du projet jusqu'à 'ready' ou 'failed' (timeout 180s pour GPU)
            start_time = time.time()
            final_project = None
            while time.time() - start_time < 180:
                res_p = await ac.get(f"/projects/{proj_id}")
                assert res_p.status_code == 200
                p = res_p.json()
                status = p["status"]
                step = p.get("step")
                prog = p.get("progress", 0)
                print(f"[E2E] Status: {status} | Step: {step} | Progress: {prog:.1%}")
                if status in ("ready", "failed"):
                    final_project = p
                    break
                await asyncio.sleep(2)

            assert final_project is not None, "Timeout waiting for pipeline execution"
            assert final_project["status"] == "ready", f"Pipeline failed: {final_project.get('error')}"

            # 4. Vérifier les clips retournés par l'API
            res_clips = await ac.get(f"/projects/{proj_id}/clips")
            assert res_clips.status_code == 200
            clips = res_clips.json()
            assert len(clips) >= 1, "At least one clip must be generated"

            clip = clips[0]
            assert clip["status"] == "ready"
            assert clip["layout"]["name"] == "facecam_top"
            assert clip["layout"]["cam"]["x"] == pytest.approx(0.739, abs=0.01)

            # Vérifier que le fichier vidéo du clip existe bien sur disque et est lisible
            clip_file = Path(clip["file_path"])
            if not clip_file.is_absolute():
                clip_file = settings.data_dir / "projects" / proj_id / clip_file
            assert clip_file.exists(), f"Rendered clip file {clip_file} not found"
            assert clip_file.stat().st_size > 100_000, f"Rendered clip too small: {clip_file.stat().st_size} bytes"

            print(f"\n[E2E Succès] Clip rendu : {clip_file} ({clip_file.stat().st_size} octets)")

