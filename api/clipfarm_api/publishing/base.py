from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class AccountInfo:
    platform_account_id: str
    name: str
    avatar_url: Optional[str] = None
    tokens: dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PublicationPayload:
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    privacy: str = "private"  # private, unlisted, public
    made_for_kids: bool = False
    category_id: str = "22"
    scheduled_at: Optional[datetime] = None
    cover_image_path: Optional[Path] = None
    extra_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublicationResult:
    success: bool
    external_id: str = ""
    url: str = ""
    status: str = "published"
    error: Optional[str] = None


@dataclass
class PublicationStatusResult:
    status: str  # published, processing, failed
    external_id: str
    url: Optional[str] = None
    error: Optional[str] = None


class Publisher(ABC):
    """Interface commune pour tous les adaptateurs de publication."""

    @abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        """Génère l'URL d'autorisation OAuth."""
        pass

    @abstractmethod
    async def connect(self, code: str, redirect_uri: str, **kwargs) -> AccountInfo:
        """Échange le code d'autorisation contre des jetons et récupère les infos du compte."""
        pass

    @abstractmethod
    async def refresh_token(self, tokens: dict[str, Any]) -> dict[str, Any]:
        """Rafraîchit les jetons d'accès si nécessaire."""
        pass

    @abstractmethod
    def validate(self, post: PublicationPayload, video_path: Optional[Path] = None) -> ValidationResult:
        """Valide strictement les limites de la plateforme avant l'envoi."""
        pass

    @abstractmethod
    async def upload(self, tokens: dict[str, Any], post: PublicationPayload, video_path: Path) -> PublicationResult:
        """Envoie la vidéo et ses métadonnées à la plateforme."""
        pass

    @abstractmethod
    async def status(self, tokens: dict[str, Any], external_id: str) -> PublicationStatusResult:
        """Vérifie le statut de traitement d'une publication."""
        pass
