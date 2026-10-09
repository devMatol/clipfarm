from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field
from clipfarm_engine.config import Settings as EngineSettings, _env, _data_dir


class ApiSettings(BaseModel):
    database_url: str = Field(default_factory=lambda: _env("DATABASE_URL", "postgresql://clipfarm:clipfarm@localhost:5432/clipfarm"))
    data_dir: Path = Field(default_factory=lambda: _data_dir())
    upload_dir: Path = Field(default_factory=lambda: _data_dir() / "uploads")
    allowed_cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    secret_key: str = Field(default_factory=lambda: _env("CLIPFARM_SECRET_KEY", ""))
    youtube_client_id: str = Field(default_factory=lambda: _env("YOUTUBE_CLIENT_ID", ""))
    youtube_client_secret: str = Field(default_factory=lambda: _env("YOUTUBE_CLIENT_SECRET", ""))
    tiktok_client_key: str = Field(default_factory=lambda: _env("TIKTOK_CLIENT_KEY", ""))
    tiktok_client_secret: str = Field(default_factory=lambda: _env("TIKTOK_CLIENT_SECRET", ""))
    meta_app_id: str = Field(default_factory=lambda: _env("META_APP_ID", ""))
    meta_app_secret: str = Field(default_factory=lambda: _env("META_APP_SECRET", ""))
    postiz_api_url: str = Field(default_factory=lambda: _env("POSTIZ_API_URL", "http://localhost:4200"))
    postiz_api_key: str = Field(default_factory=lambda: _env("POSTIZ_API_KEY", ""))
    public_base_url: str = Field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://localhost:8000"))


settings = ApiSettings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
