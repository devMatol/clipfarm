from datetime import datetime, timezone
from typing import Any, Optional, List
from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel


class ClipBase(SQLModel):
    project_id: str = Field(foreign_key="projects.id", index=True)
    index: int
    start: float
    end: float
    title: str = ""
    hook: str = ""
    reason: str = ""
    scores: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    final_score: float = 0.0
    layout: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    captions: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    edit_plan: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    file_path: str
    status: str = Field(default="ready")


class Clip(ClipBase, table=True):
    __tablename__ = "clips"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    project: Optional["Project"] = Relationship(back_populates="clips")


class ProjectBase(SQLModel):
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    status: str = Field(default="queued")
    progress: float = Field(default=0.0)
    step: str = Field(default="queued")
    duration: Optional[float] = None
    settings_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error: Optional[str] = None


class Project(ProjectBase, table=True):
    __tablename__ = "projects"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    clips: List[Clip] = Relationship(back_populates="project", cascade_delete=True)


class CamPreset(SQLModel, table=True):
    __tablename__ = "cam_presets"

    id: Optional[int] = Field(default=None, primary_key=True)
    channel: str = Field(index=True)
    rect: dict[str, float] = Field(sa_column=Column(JSON))


# Schémas DTO pour requêtes et réponses Pydantic
class ProjectCreateUrl(SQLModel):
    url: str
    layout: str = "auto"
    format: str = "9:16"
    cam: Optional[dict[str, float]] = None
    captions: Optional[str] = "punchy"
    max_clips: int = 5
    min_clip_s: Optional[float] = None
    max_clip_s: Optional[float] = None
    llm: Optional[str] = None
    skip_if_subtitles_present: bool = True


class ClipUpdate(SQLModel):
    title: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    words: Optional[list[dict[str, Any]]] = None


class ProjectRenderRequest(SQLModel):
    clip_id: Optional[str] = None
    layout: Optional[str] = None
    format: Optional[str] = None
    cam: Optional[dict[str, float]] = None
    captions: Optional[str] = None


class ClipRenderRequest(SQLModel):
    layout: Optional[str] = None
    format: Optional[str] = None
    cam: Optional[dict[str, float]] = None
    captions: Optional[str] = None


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: str = Field(primary_key=True)
    platform: str = Field(index=True)  # youtube, tiktok, instagram, postiz
    platform_account_id: str = Field(index=True)
    name: str = ""
    avatar_url: Optional[str] = None
    encrypted_tokens: str  # Chiffré Fernet, jamais renvoyé par l'API
    expires_at: Optional[datetime] = None
    status: str = Field(default="connected")  # connected, expiring_soon, needs_reconnect
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountOut(SQLModel):
    """DTO public pour l'exposition API : aucun jeton ni secret n'est présent."""
    id: str
    platform: str
    platform_account_id: str
    name: str
    avatar_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    status: str
    created_at: datetime


class Publication(SQLModel, table=True):
    __tablename__ = "publications"

    id: str = Field(primary_key=True)
    clip_id: str = Field(foreign_key="clips.id", index=True)
    account_id: str = Field(foreign_key="accounts.id", index=True)
    platform: str = Field(index=True)
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    scheduled_at: Optional[datetime] = None
    status: str = Field(default="draft")  # draft, scheduled, uploading, processing, published, failed
    external_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    attempts: int = Field(default=0)
    idempotency_key: str = Field(default="", index=True)
    rights_confirmed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None


class PublicationCreate(SQLModel):
    clip_id: Optional[str] = None
    account_id: Optional[str] = None
    platform: str = "youtube"
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    privacy: str = "private"  # private, unlisted, public
    made_for_kids: bool = False
    category_id: str = "22"
    rights_confirmed: bool = False
    publish_now: bool = True
    scheduled_at: Optional[datetime] = None
    predictive_score: Optional[int] = None
    algorithmic_reason: Optional[str] = None


class PublicationOut(SQLModel):
    id: str
    clip_id: str
    account_id: str
    platform: str
    metadata_json: dict[str, Any]
    scheduled_at: Optional[datetime]
    status: str
    external_id: Optional[str]
    url: Optional[str]
    error: Optional[str]
    rights_confirmed: bool
    created_at: datetime
    published_at: Optional[datetime]


