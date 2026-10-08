from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from clipfarm_api.config import settings
from clipfarm_api.models import Clip, Project


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "clipfarm-api"}


def test_create_project_defer_error_sets_failed(client: TestClient, session: Session):
    """Point 1 : Si defer() échoue, plus d'except pass : le projet passe en failed et renvoie 500."""
    with patch("clipfarm_api.routers.projects.process_project.defer_async", side_effect=RuntimeError("Procrastinate broker unreachable")):
        payload = {"url": "https://www.youtube.com/watch?v=fails", "layout": "center"}
        response = client.post("/projects", json=payload)
        assert response.status_code == 500

    # Vérifier que le statut en DB est 'failed' avec le message
    proj = session.exec(select(Project).where(Project.source_url == "https://www.youtube.com/watch?v=fails")).first()
    assert proj is not None
    assert proj.status == "failed"
    assert "Procrastinate broker unreachable" in proj.error


def test_unique_upload_filenames(client: TestClient):
    """Point 8 : Uploader deux fichiers avec le même nom génère des fichiers uniques sans écrasement."""
    fake_video1 = b"video_content_1"
    files1 = {"file": ("video.mp4", io.BytesIO(fake_video1), "video/mp4")}
    with patch("clipfarm_api.routers.projects.process_project.defer_async"):
        res1 = client.post("/projects/upload", files=files1, data={"layout": "center"})
        assert res1.status_code == 201
        p1 = res1.json()["project"]

    fake_video2 = b"video_content_2_longer"
    files2 = {"file": ("video.mp4", io.BytesIO(fake_video2), "video/mp4")}
    with patch("clipfarm_api.routers.projects.process_project.defer_async"):
        res2 = client.post("/projects/upload", files=files2, data={"layout": "center"})
        assert res2.status_code == 201
        p2 = res2.json()["project"]

    assert p1["id"] != p2["id"]
    assert p1["source_path"] != p2["source_path"]
    assert Path(p1["source_path"]).exists()
    assert Path(p2["source_path"]).exists()


def test_words_structure_and_patch_and_rerender(client: TestClient, session: Session):
    """Points 2 & 3 : Word a start, end, text, prob. Test GET words, PATCH words et persistance de la cam."""
    proj_id = "test_words_proj"
    pdir = settings.data_dir / "projects" / proj_id
    pdir.mkdir(parents=True, exist_ok=True)

    # Créer un vrai words.json avec la structure du moteur (start, end, text, prob)
    words_data = [
        {"start": 10.0, "end": 10.5, "text": "Bienvenue", "prob": 0.99},
        {"start": 10.6, "end": 11.2, "text": "dans", "prob": 0.95},
        {"start": 11.3, "end": 12.0, "text": "ClipFarm", "prob": 0.98},
    ]
    (pdir / "words.json").write_text(json.dumps(words_data), encoding="utf-8")

    project = Project(id=proj_id, status="ready", progress=1.0)
    session.add(project)

    cam_dict = {"x": 0.72, "y": 0.05, "w": 0.25, "h": 0.25}
    clip = Clip(
        id=f"{proj_id}_1",
        project_id=proj_id,
        index=1,
        start=10.0,
        end=12.0,
        title="Intro",
        layout={"name": "facecam_top", "fmt": "9:16", "cam": cam_dict},
        captions={"preset": "punchy"},
        file_path="clips/01.mp4",
        status="ready",
    )
    session.add(clip)
    session.commit()

    # 1. Tester GET /clips/{id}/words
    res_words = client.get(f"/clips/{proj_id}_1/words")
    assert res_words.status_code == 200
    returned_words = res_words.json()
    assert len(returned_words) == 3
    # Vérifier que les clés sont text, start, end, prob (et PAS word ni score)
    assert returned_words[0]["text"] == "Bienvenue"
    assert returned_words[0]["prob"] == 0.99
    assert "word" not in returned_words[0]

    # 2. Tester PATCH /clips/{id} avec correction de mot
    modified_words = [
        {"start": 10.0, "end": 10.5, "text": "Salut", "prob": 0.99},
        {"start": 10.6, "end": 11.2, "text": "sur", "prob": 0.95},
        {"start": 11.3, "end": 12.0, "text": "ClipFarm", "prob": 0.98},
    ]
    res_patch = client.patch(f"/clips/{proj_id}_1", json={"words": modified_words, "title": "Intro Corrigée"})
    assert res_patch.status_code == 200

    # Vérifier que le fichier clip_1_words.json a été sauvegardé avec text et prob
    custom_words_file = pdir / "clip_1_words.json"
    assert custom_words_file.exists()
    saved_words = json.loads(custom_words_file.read_text(encoding="utf-8"))
    assert saved_words[0]["text"] == "Salut"

    # 3. Tester POST /projects/{id}/render (Re-rendu ciblé d'un clip)
    with patch("clipfarm_api.routers.clips.rerender_project_task.defer_async") as mock_defer:
        res_render = client.post(f"/projects/{proj_id}/render", json={"clip_id": f"{proj_id}_1"})
        assert res_render.status_code == 202
        assert mock_defer.called
        call_kwargs = mock_defer.call_args[1]
        assert call_kwargs["clip_id"] == f"{proj_id}_1"

    session.refresh(clip)
    session.refresh(project)
    # Le clip est marqué en 'rendering', mais le projet reste intact en 'ready' !
    assert clip.status == "rendering"
    assert project.status == "ready"


def test_clip_rerender_and_time_extension_words(client: TestClient, session: Session):
    """Vérifie que l'ajout de temps à un clip résout et ajoute automatiquement les sous-titres de la nouvelle portion."""
    proj_id = "test_time_ext_proj"
    pdir = settings.data_dir / "projects" / proj_id
    pdir.mkdir(parents=True, exist_ok=True)

    # Transcription complète de la vidéo (words.json)
    full_words = [
        {"start": 5.0, "end": 5.8, "text": "Au début", "prob": 0.99},
        {"start": 10.0, "end": 10.5, "text": "Bienvenue", "prob": 0.99},
        {"start": 11.0, "end": 11.5, "text": "ici", "prob": 0.95},
        {"start": 15.0, "end": 15.8, "text": "A la fin", "prob": 0.99},
    ]
    (pdir / "words.json").write_text(json.dumps(full_words), encoding="utf-8")

    project = Project(id=proj_id, status="ready", progress=1.0)
    session.add(project)

    # Clip initial couvrant uniquement [10.0, 12.0]
    clip = Clip(
        id=f"{proj_id}_1",
        project_id=proj_id,
        index=1,
        start=10.0,
        end=12.0,
        title="Moment",
        layout={"name": "center", "fmt": "9:16"},
        captions={"preset": "punchy"},
        file_path="clips/01.mp4",
        status="ready",
    )
    session.add(clip)
    session.commit()

    # 1. Requête GET words sur la plage initiale
    res1 = client.get(f"/clips/{proj_id}_1/words")
    assert res1.status_code == 200
    words1 = res1.json()
    assert len(words1) == 2
    assert [w["text"] for w in words1] == ["Bienvenue", "ici"]

    # 2. Modification du texte d'un mot existant par l'utilisateur
    words1[0]["text"] = "Bienvenue modifié"
    patch_res = client.patch(f"/clips/{proj_id}_1", json={"words": words1})
    assert patch_res.status_code == 200

    # 3. Extension de la durée du clip (ajout de temps avant: 5.0s et après: 16.0s)
    res_expanded = client.get(f"/clips/{proj_id}_1/words?start=4.5&end=16.0")
    assert res_expanded.status_code == 200
    words_expanded = res_expanded.json()
    # Doit contenir les 4 mots, dont le mot personnalisé préservé !
    assert len(words_expanded) == 4
    texts = [w["text"] for w in words_expanded]
    assert "Au début" in texts
    assert "Bienvenue modifié" in texts  # correction utilisateur préservée !
    assert "ici" in texts
    assert "A la fin" in texts  # nouvelle portion temporelle incluse !

    # 4. Route dédiée POST /clips/{id}/render
    with patch("clipfarm_api.routers.clips.rerender_project_task.defer_async") as mock_defer:
        res_clip_render = client.post(f"/clips/{proj_id}_1/render", json={"layout": "blur"})
        assert res_clip_render.status_code == 202
        assert mock_defer.called
        assert mock_defer.call_args[1]["clip_id"] == f"{proj_id}_1"

    session.refresh(clip)
    session.refresh(project)
    assert clip.status == "rendering"
    assert project.status == "ready"



def test_set_cam_for_url_project(client: TestClient, session: Session):
    """Point 4 : Valider la facecam via set-cam débloque le projet awaiting_cam."""
    p = Project(id="await_proj", source_url="https://youtube.com/test", status="awaiting_cam", step="awaiting_cam")
    session.add(p)
    session.commit()

    with patch("clipfarm_api.routers.projects.process_project.defer_async") as mock_defer:
        cam_payload = {"x": 0.7, "y": 0.1, "w": 0.2, "h": 0.2}
        res = client.post("/projects/await_proj/set-cam", json=cam_payload)
        assert res.status_code == 200
        assert mock_defer.called

    session.refresh(p)
    assert p.status == "queued"
    assert p.settings_json["cam"] == cam_payload


def test_media_streaming_and_range(client: TestClient):
    media_file = settings.data_dir / "sample.mp4"
    content = b"0123456789" * 100
    media_file.write_bytes(content)

    res_full = client.get("/media/sample.mp4")
    assert res_full.status_code == 200
    assert len(res_full.content) == 1000

    res_range = client.get("/media/sample.mp4", headers={"Range": "bytes=0-99"})
    assert res_range.status_code == 206
    assert res_range.headers["Content-Range"] == "bytes 0-99/1000"
    assert len(res_range.content) == 100
    assert res_range.content == content[:100]
