from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from clipfarm_api.config import settings
from clipfarm_api.models import Account, Clip, Project, Publication
from clipfarm_api.publishing.base import PublicationPayload
from clipfarm_api.publishing.crypto import decrypt_tokens, encrypt_tokens
from clipfarm_api.publishing.sanitizer import sanitize_video_for_publishing
from clipfarm_api.publishing.youtube import YouTubePublisher


def test_crypto_fernet_tokens():
    """Vérifie le chiffrement symétrique Fernet et le déchiffrement exact des jetons."""
    data = {
        "access_token": "ya29.secret_access_token_12345",
        "refresh_token": "1//04secret_refresh_token_67890",
        "expires_in": 3600,
    }
    encrypted = encrypt_tokens(data)
    # Le jeton brut ne doit jamais apparaître en clair dans le texte chiffré
    assert "ya29" not in encrypted
    assert "secret" not in encrypted

    # Déchiffrement
    decrypted = decrypt_tokens(encrypted)
    assert decrypted["access_token"] == data["access_token"]
    assert decrypted["refresh_token"] == data["refresh_token"]


def test_youtube_validation_strict_limits(tmp_path: Path):
    """Validation stricte des contraintes YouTube Shorts (titre, description, etc.)."""
    pub = YouTubePublisher()

    # 1. Titre trop long (> 100 caractères)
    too_long = "C" * 105
    payload_bad = PublicationPayload(title=too_long)
    res_bad = pub.validate(payload_bad)
    assert not res_bad.valid
    assert any("100 caractères" in e for e in res_bad.errors)

    # 2. Titre vide
    res_empty = pub.validate(PublicationPayload(title="   "))
    assert not res_empty.valid
    assert any("obligatoire" in e for e in res_empty.errors)

    # 3. Titre et description valides
    payload_ok = PublicationPayload(
        title="Super Action #Shorts",
        description="Une courte vidéo captivante.",
        tags=["shorts", "gaming"],
        privacy="unlisted",
        made_for_kids=False,
    )
    res_ok = pub.validate(payload_ok)
    assert res_ok.valid
    assert len(res_ok.errors) == 0


def test_accounts_endpoints_and_oauth_callback(client: TestClient, session: Session):
    """Teste la liste des comptes, le callback OAuth et la déconnexion."""
    # Mock des appels HTTP de Google OAuth et de YouTube Data API
    mock_token_resp = httpx.Response(
        status_code=200,
        json={"access_token": "mock_at", "refresh_token": "mock_rt", "expires_in": 3600},
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )
    mock_channel_resp = httpx.Response(
        status_code=200,
        json={
            "items": [
                {
                    "id": "UC_channel_12345",
                    "snippet": {
                        "title": "Ma Chaîne YouTube",
                        "thumbnails": {"default": {"url": "https://yt.com/avatar.jpg"}},
                    },
                }
            ]
        },
        request=httpx.Request("GET", "https://www.googleapis.com/youtube/v3/channels"),
    )

    async def mock_post(url, **kwargs):
        return mock_token_resp

    async def mock_get(url, **kwargs):
        return mock_channel_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post), patch("httpx.AsyncClient.get", side_effect=mock_get):
        res_cb = client.post(
            "/accounts/connect/youtube/callback",
            json={"code": "auth_code_xyz", "redirect_uri": "http://localhost:3000/accounts/callback"},
        )
        assert res_cb.status_code == 201
        data = res_cb.json()
        assert data["id"] == "yt_UC_channel_12345"
        assert data["name"] == "Ma Chaîne YouTube"
        assert data["avatar_url"] == "https://yt.com/avatar.jpg"
        # Les jetons ne sont JAMAIS renvoyés
        assert "tokens" not in data
        assert "encrypted_tokens" not in data

    # Vérifier l'enregistrement en DB avec jetons chiffrés
    db_acc = session.get(Account, "yt_UC_channel_12345")
    assert db_acc is not None
    assert "mock_at" not in db_acc.encrypted_tokens
    decrypted = decrypt_tokens(db_acc.encrypted_tokens)
    assert decrypted["access_token"] == "mock_at"

    # Vérifier GET /accounts
    res_list = client.get("/accounts")
    assert res_list.status_code == 200
    accounts = res_list.json()
    assert len(accounts) >= 1
    assert accounts[0]["id"] == "yt_UC_channel_12345"
    assert "tokens" not in accounts[0]

    # Tester DELETE /accounts/{id}
    res_del = client.delete("/accounts/yt_UC_channel_12345")
    assert res_del.status_code == 200
    assert session.get(Account, "yt_UC_channel_12345") is None


def test_publish_clip_rights_enforcement_and_youtube_upload(client: TestClient, session: Session, tmp_path: Path):
    """Vérifie l'obligation stricte des droits et l'envoi résumable simulé sur YouTube."""
    # Créer un compte YouTube en base
    future_exp = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    acc = Account(
        id="yt_test_acc",
        platform="youtube",
        platform_account_id="UC_test",
        name="Chaîne Test",
        encrypted_tokens=encrypt_tokens({"access_token": "valid_token", "refresh_token": "rt", "expires_at": future_exp}),
        status="connected",
    )
    session.add(acc)

    # Créer un faux clip avec vidéo
    fake_video = tmp_path / "clip.mp4"
    fake_video.write_bytes(b"\x00" * 1024)

    proj = Project(id="proj_pub", status="ready")
    session.add(proj)
    clip = Clip(
        id="proj_pub_1",
        project_id="proj_pub",
        index=1,
        start=0.0,
        end=25.0,
        file_path=str(fake_video),
        status="ready",
    )
    session.add(clip)
    session.commit()

    # 1. Tentative sans confirmation des droits -> Rejet 400
    payload_no_rights = {
        "clip_id": "proj_pub_1",
        "account_id": "yt_test_acc",
        "platform": "youtube",
        "title": "Mon super Short",
        "rights_confirmed": False,
        "publish_now": True,
    }
    res_no_rights = client.post("/clips/proj_pub_1/publish", json=payload_no_rights)
    assert res_no_rights.status_code == 400
    assert "droits" in res_no_rights.json()["detail"].lower()

    # 2. Publication réussie avec droits confirmés et mock upload YouTube
    mock_init_resp = httpx.Response(
        status_code=200,
        headers={"Location": "https://upload.youtube.com/resumable_session_url"},
        request=httpx.Request("POST", "https://upload.youtube.com"),
    )
    mock_put_resp = httpx.Response(
        status_code=200,
        json={"id": "dQw4w9WgXcQ"},
        request=httpx.Request("PUT", "https://upload.youtube.com/resumable_session_url"),
    )

    async def mock_post(url, **kwargs):
        return mock_init_resp

    async def mock_put(url, **kwargs):
        return mock_put_resp

    payload_ok = {
        "clip_id": "proj_pub_1",
        "account_id": "yt_test_acc",
        "platform": "youtube",
        "title": "Action Inouïe",
        "description": "Moment épique du live",
        "tags": ["gaming", "clip"],
        "privacy": "unlisted",
        "made_for_kids": False,
        "rights_confirmed": True,
        "publish_now": True,
    }

    with patch("httpx.AsyncClient.post", side_effect=mock_post), \
         patch("httpx.AsyncClient.put", side_effect=mock_put), \
         patch("clipfarm_api.publishing.youtube.sanitize_video_for_publishing", side_effect=lambda inp, out: inp), \
         patch("clipfarm_api.publishing.youtube.check_video_for_platform", return_value=(True, [])):
        res_pub = client.post("/clips/proj_pub_1/publish", json=payload_ok)
        assert res_pub.status_code == 201
        data = res_pub.json()
        assert data["status"] == "published"
        assert data["external_id"] == "dQw4w9WgXcQ"
        assert data["url"] == "https://youtube.com/shorts/dQw4w9WgXcQ"
        assert data["rights_confirmed"] is True

    # Vérifier l'entrée dans la table publications
    pub_entry = session.exec(select(Publication).where(Publication.external_id == "dQw4w9WgXcQ")).first()
    assert pub_entry is not None
    assert pub_entry.status == "published"
    assert pub_entry.metadata_json["title"] == "Action Inouïe"


def test_generate_publishing_metadata_multiframe_ground_truth(tmp_path: Path):
    """Vérifie que la génération de métadonnées intègre les images et le créateur vérifié sans hallucination."""
    from clipfarm_api.publishing.metadata import generate_publishing_metadata

    # Créer 2 fausses images
    img1 = tmp_path / "frame1.jpg"
    img1.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9")
    img2 = tmp_path / "frame2.jpg"
    img2.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9")

    mock_llm_response = json.dumps({
        "title": "Anyme et Mastu dans le défi ultime",
        "description": "Anyme TV et Mastu relèvent le défi !\n\nUne ambiance de folie.\n\nQuel est votre moment préféré ?",
        "tags": ["Anyme", "Mastu", "Défi", "Humour"],
        "hashtags": ["#Shorts", "#Mastu", "#Anyme"]
    })

    with patch("clipfarm_api.publishing.metadata.ask_gemini", return_value=mock_llm_response) as mock_gemini:
        res = generate_publishing_metadata(
            clip_title="Défi Mastu",
            hook="Regardez ce qui arrive",
            transcript="On est avec Mastu dans la maison",
            platform="youtube",
            image_paths=[img1, img2],
            creator_name="Anyme TV",
            source_title="Je REMPLIS ma MAISON de BOULES avec MASTU !",
        )

        assert mock_gemini.called
        call_args = mock_gemini.call_args
        prompt_sent = call_args[0][0]
        images_sent = call_args[1].get("images_b64")

        # Vérifier que le créateur et le titre sont bien dans le prompt
        assert "Anyme TV" in prompt_sent
        assert "Je REMPLIS ma MAISON de BOULES avec MASTU !" in prompt_sent
        assert "INTERDICTION ABSOLUE ET FORMELLE d'inventer des créateurs" in prompt_sent
        assert len(images_sent) == 2

        # Vérifier le résultat
        assert "Mastu" in res["title"]
        assert "Anyme" in res["title"]
        assert "#Shorts" in res["title"]


def test_get_clip_metadata_endpoint_reads_source_info(client: TestClient, session: Session, tmp_path: Path):
    """Vérifie que l'endpoint /clips/{id}/metadata extrait les infos de source.info.json."""
    p = Project(id="proj_src_meta", status="ready")
    session.add(p)
    c = Clip(
        id="proj_src_meta_1",
        project_id="proj_src_meta",
        index=1,
        start=10.0,
        end=30.0,
        title="Moment Drôle",
        hook="Accroche drôle",
        file_path=str(tmp_path / "clip.mp4"),
        status="ready"
    )
    session.add(c)
    session.commit()

    pdir = settings.data_dir / "projects" / "proj_src_meta"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "metadata.json").write_text(json.dumps({
        "uploader": "JoueurDuGrenier",
        "title": "JDG Hors-Série Jeux en Vrac"
    }), encoding="utf-8")

    mock_llm_response = json.dumps({
        "title": "JDG pète un câble sur ce jeu rétro",
        "description": "Joueur Du Grenier découvre un jeu infâme.\n\nVous vous rappelez de cette pépite ?",
        "tags": ["JDG", "JoueurDuGrenier", "Retro"],
        "hashtags": ["#Shorts", "#JDG"]
    })

    with patch("clipfarm_api.publishing.metadata.ask_gemini", return_value=mock_llm_response) as mock_gemini:
        res = client.post("/clips/proj_src_meta_1/metadata", json={"platform": "youtube"})
        assert res.status_code == 200
        data = res.json()
        assert "JDG" in data["title"]
        call_prompt = mock_gemini.call_args[0][0]
        assert "JoueurDuGrenier" in call_prompt

