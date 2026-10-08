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
