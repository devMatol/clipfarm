from __future__ import annotations

import pytest
from pathlib import Path
from clipfarm_api.publishing.base import PublicationPayload
from clipfarm_api.publishing.postiz import PostizPublisher


def test_postiz_disabled_by_default(monkeypatch):
    monkeypatch.setattr("clipfarm_api.publishing.postiz.settings.postiz_api_key", "")
    pub = PostizPublisher()
    assert not pub.is_enabled()
    res = pub.validate(PublicationPayload(title="Test", description="Desc"))
    assert not res.valid
    assert "POSTIZ_API_KEY" in res.errors[0]


def test_postiz_enabled_when_key_set(monkeypatch):
    monkeypatch.setattr("clipfarm_api.publishing.postiz.settings.postiz_api_key", "test_key_123")
    pub = PostizPublisher()
    assert pub.is_enabled()
    res = pub.validate(PublicationPayload(title="Mon Titre TikTok", description="Desc #TikTok"))
    assert res.valid
    assert len(res.errors) == 0


@pytest.mark.asyncio
async def test_postiz_mock_upload():
    pub = PostizPublisher()
    tokens = {"access_token": "mock_access_token_dev"}
    payload = PublicationPayload(
        title="Clip TikTok #Viral",
        description="Une super description #fyp",
        tags=["tiktok", "viral"],
    )
    # Fichier factice
    import tempfile
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
