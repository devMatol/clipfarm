from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from clipfarm_api.main import app
from clipfarm_api.publishing.base import PublicationPayload
from clipfarm_api.publishing.tiktok import TikTokPublisher
from httpx import ASGITransport, AsyncClient


def test_tiktok_auth_url_and_configured(monkeypatch):
    monkeypatch.setattr("clipfarm_api.publishing.tiktok.settings.tiktok_client_key", "mock_key")
    monkeypatch.setattr("clipfarm_api.publishing.tiktok.settings.tiktok_client_secret", "mock_secret")

    pub = TikTokPublisher()
    assert pub.is_configured()

    auth_url = pub.get_auth_url("http://localhost:3000/accounts/callback")
    assert "https://www.tiktok.com/v2/auth/authorize/" in auth_url
    assert "client_key=mock_key" in auth_url
    assert "redirect_uri=" in auth_url


def test_tiktok_validation():
    pub = TikTokPublisher(client_key="k", client_secret="s")

    # Titre manquant
    res = pub.validate(PublicationPayload(title=""))
    assert not res.valid
    assert any("titre" in e.lower() for e in res.errors)

    # Titre valide
    res2 = pub.validate(PublicationPayload(title="Mon Super Clip TikTok", description="Description #fyp #pourtoi"))
    assert res2.valid
    assert len(res2.errors) == 0


@pytest.mark.asyncio
async def test_tiktok_mock_upload():
    pub = TikTokPublisher(client_key="k", client_secret="s")
    tokens = {"access_token": "mock_access_token_dev"}
    payload = PublicationPayload(
        title="Clip TikTok #Viral",
        description="Regarde ce moment épique #gaming #pourtoi",
        tags=["tiktok", "viral"],
    )

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\x00" * 1024)
        tmp_path = Path(f.name)

    try:
        res = await pub.upload(tokens, payload, tmp_path)
        assert res.success
        assert res.external_id is not None
        assert "tiktok.com" in res.url
    finally:
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_tiktok_accounts_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Création d'un compte de test TikTok
        res = await client.post("/accounts/test-account?platform=tiktok&name=TikTok%20Test%20Account")
        assert res.status_code == 201
        data = res.json()
        assert data["platform"] == "tiktok"
        assert "TikTok Test Account" in data["name"]

        account_id = data["id"]

        # Liste des comptes
        list_res = await client.get("/accounts")
        assert list_res.status_code == 200
        accounts = list_res.json()
        assert any(a["id"] == account_id for a in accounts)

        # Nettoyage
        del_res = await client.delete(f"/accounts/{account_id}")
        assert del_res.status_code == 200
