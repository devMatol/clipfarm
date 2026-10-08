from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import httpx

from ..config import settings
from .base import (
    AccountInfo,
    PublicationPayload,
    PublicationResult,
    PublicationStatusResult,
    Publisher,
    ValidationResult,
)


class PostizPublisher(Publisher):
    """
    Adaptateur optionnel pour Postiz (service auto-hébergé séparé AGPL-3.0).
    Appelé exclusivement par son API REST publique. Aucun code Postiz n'est importé.
    Désactivé par défaut tant que POSTIZ_API_URL et POSTIZ_API_KEY ne sont pas configurés.
    """

    def __init__(self):
        self.api_url = settings.postiz_api_url.rstrip("/")
        self.api_key = settings.postiz_api_key

    def is_enabled(self) -> bool:
        return bool(self.api_url and self.api_key)

    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        if not self.is_enabled():
            raise RuntimeError("Postiz est désactivé par défaut. Définissez POSTIZ_API_URL et POSTIZ_API_KEY dans votre .env.")
        return f"{self.api_url}/integrations"

    async def connect(self, code: str, redirect_uri: str, **kwargs) -> AccountInfo:
        if not self.is_enabled():
            raise RuntimeError("Postiz n'est pas configuré.")
        return AccountInfo(
            platform_account_id="postiz_default",
            name="Postiz Integration",
            tokens={"api_key": self.api_key},
        )

    async def refresh_token(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def validate(self, post: PublicationPayload, video_path: Optional[Path] = None) -> ValidationResult:
        if not self.is_enabled():
            return ValidationResult(
                valid=False,
                errors=["Le service Postiz est désactivé par défaut (POSTIZ_API_URL ou POSTIZ_API_KEY non définis)."],
            )
        return ValidationResult(valid=True)

    async def upload(self, tokens: dict[str, Any], post: PublicationPayload, video_path: Path) -> PublicationResult:
        if not self.is_enabled():
            return PublicationResult(success=False, error="Postiz n'est pas configuré.")

        # Appel de l'API publique de Postiz pour créer la publication
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            body = {
                "title": post.title,
                "content": post.description,
                "tags": post.tags,
                "scheduleDate": post.scheduled_at.isoformat() if post.scheduled_at else None,
            }
            try:
                res = await client.post(f"{self.api_url}/api/v1/posts", headers=headers, json=body)
                if res.status_code not in (200, 201):
                    return PublicationResult(success=False, error=f"Erreur API Postiz ({res.status_code}): {res.text}")
                data = res.json()
                post_id = data.get("id", "")
                return PublicationResult(success=True, external_id=post_id, url=f"{self.api_url}/posts/{post_id}")
            except Exception as exc:
                return PublicationResult(success=False, error=f"Impossible de contacter Postiz: {exc}")

    async def status(self, tokens: dict[str, Any], external_id: str) -> PublicationStatusResult:
        if not self.is_enabled():
            return PublicationStatusResult(status="failed", external_id=external_id, error="Postiz non configuré")
        return PublicationStatusResult(status="published", external_id=external_id)
