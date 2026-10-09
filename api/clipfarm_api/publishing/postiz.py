from __future__ import annotations

import logging
from datetime import datetime, timezone
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
from .sanitizer import sanitize_video_for_publishing

logger = logging.getLogger("clipfarm_api.postiz")


class PostizPublisher(Publisher):
    """
    Adaptateur pour Postiz (service auto-hébergé séparé AGPL-3.0).
    Appelé exclusivement par son API REST publique standard (/public/v1).
    Aucun code Postiz n'est importé dans ClipFarm.
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        raw_url = (api_url or settings.postiz_api_url or "http://localhost:4200").rstrip("/")
        if not raw_url.endswith("/public/v1") and not raw_url.endswith("/api/v1"):
            self.base_url = f"{raw_url}/public/v1"
        else:
            self.base_url = raw_url
        self.raw_root_url = raw_url.replace("/public/v1", "").replace("/api/v1", "")
        self.api_key = api_key or settings.postiz_api_key

    def is_enabled(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def get_auth_headers(self) -> dict[str, str]:
        key = self.api_key.strip() if self.api_key else ""
        return {
            "Authorization": key,
            "Accept": "application/json",
        }

    async def check_health(self) -> dict[str, Any]:
        """Vérifie l'état de connexion de l'instance Postiz et la validité de la clé API."""
        is_server_up = False
        try:
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                ping_res = await client.get(self.raw_root_url)
                if ping_res.status_code in (200, 301, 302, 307, 308):
                    is_server_up = True
        except Exception:
            is_server_up = False

        if not self.api_key:
            return {
                "configured": is_server_up,
                "reachable": is_server_up,
                "authenticated": False,
                "url": self.raw_root_url,
                "message": (
                    "Serveur Postiz actif en local (port 4200) ! Ajoutez votre clé POSTIZ_API_KEY dans .env pour synchroniser."
                    if is_server_up
                    else "Serveur Postiz non détecté sur le port 4200."
                ),
                "channels": [],
            }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/integrations", headers=self.get_auth_headers())
                if res.status_code == 200:
                    data = res.json()
                    channels = data if isinstance(data, list) else data.get("integrations", [])
                    return {
                        "configured": True,
                        "reachable": True,
                        "authenticated": True,
                        "url": self.raw_root_url,
                        "message": f"Connecté à Postiz ({len(channels)} canaux détectés).",
                        "channels": channels,
                    }
                elif res.status_code in (401, 403):
                    return {
                        "configured": True,
                        "reachable": True,
                        "authenticated": False,
                        "url": self.raw_root_url,
                        "message": "Postiz joignable mais clé API invalide ou refusée.",
                        "channels": [],
                    }
                else:
                    return {
                        "configured": True,
                        "reachable": True,
                        "authenticated": False,
                        "url": self.raw_root_url,
                        "message": f"Réponse inattendue de Postiz (code {res.status_code}).",
                        "channels": [],
                    }
        except Exception as exc:
            return {
                "configured": True,
                "reachable": False,
                "authenticated": False,
                "url": self.raw_root_url,
                "message": f"Serveur Postiz injoignable ({exc}). Assurez-vous qu'il est démarré.",
                "channels": [],
            }

    async def list_integrations(self) -> list[dict[str, Any]]:
        """Récupère la liste des réseaux sociaux (canaux) connectés dans Postiz."""
        if not self.is_enabled():
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/integrations", headers=self.get_auth_headers())
                if res.status_code == 200:
                    data = res.json()
                    return data if isinstance(data, list) else data.get("integrations", [])
        except Exception as exc:
            logger.warning("Erreur lors de la récupération des intégrations Postiz: %s", exc)
        return []

    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        return f"{self.raw_root_url}/integrations"

    async def connect(self, code: str, redirect_uri: str, **kwargs) -> AccountInfo:
        return AccountInfo(
            platform_account_id="postiz_default",
            name="Postiz Integration",
            tokens={"api_key": self.api_key},
        )

    async def refresh_token(self, tokens: dict[str, Any]) -> dict[str, Any]:
        return tokens

    def validate(self, post: PublicationPayload, video_path: Optional[Path] = None) -> ValidationResult:
        errors = []
        warnings = []

        if not self.is_enabled():
            errors.append("Le service Postiz est désactivé par défaut (POSTIZ_API_KEY non défini).")

        if not post.title:
            errors.append("Le titre est requis pour publier sur TikTok / Postiz.")

        if video_path and video_path.exists():
            # TikTok recommande max 10 minutes, format vertical ou carré
            from .youtube import check_video_for_platform
            valid_vid, vid_errs = check_video_for_platform(video_path, max_duration_s=600.0, allow_square=True)
            if not valid_vid:
                errors.extend(vid_errs)

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    async def upload_media(self, video_path: Path) -> tuple[Optional[str], Optional[str]]:
        """Téléverse le fichier vidéo vers Postiz via l'API multipart /upload."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = self.get_auth_headers()
            with open(video_path, "rb") as f:
                files = {"file": (video_path.name, f, "video/mp4")}
                res = await client.post(f"{self.base_url}/upload", headers=headers, files=files)
                if res.status_code not in (200, 201):
                    return None, f"Erreur upload média Postiz ({res.status_code}): {res.text}"
                data = res.json()
                media_id = data.get("id") or data.get("path") or data.get("url")
                return media_id, None

    async def upload(self, tokens: dict[str, Any], post: PublicationPayload, video_path: Path) -> PublicationResult:
        """Publie ou programme un clip via l'API REST de Postiz."""
        # 1. Gestion du compte de test / mock local
        if tokens.get("access_token") == "mock_access_token_dev" or tokens.get("is_mock"):
            import uuid
            mock_id = f"tt_mock_{uuid.uuid4().hex[:8]}"
            logger.info("[Postiz Mock] Simulation d'envoi réussi pour le clip sur TikTok.")
            return PublicationResult(
                success=True,
                external_id=mock_id,
                url=f"https://www.tiktok.com/@clipfarm_demo/video/{uuid.uuid4().int % 10000000000}",
            )

        if not self.is_enabled():
            return PublicationResult(
                success=False,
                error="Postiz n'est pas configuré. Veuillez renseigner POSTIZ_API_KEY dans votre fichier .env.",
            )

        # 2. Nettoyage strict des métadonnées vidéo (suppression GPS, auteur)
        sanitized_dir = video_path.parent / "sanitized"
        sanitized_dir.mkdir(parents=True, exist_ok=True)
        target_clean = sanitized_dir / f"clean_{video_path.name}"
        clean_video = sanitize_video_for_publishing(video_path, target_clean)

        # 3. Upload du média dans Postiz
        media_id, err = await self.upload_media(clean_video)
        if not media_id:
            return PublicationResult(success=False, error=err or "Échec d'upload vidéo vers Postiz.")

        # 4. Identification du canal Postiz
        integration_id = tokens.get("integration_id") or tokens.get("channel_id")
        if not integration_id:
            # Récupérer le premier canal TikTok disponible dans Postiz
            integrations = await self.list_integrations()
            for it in integrations:
                identifier = (it.get("identifier") or it.get("provider") or "").lower()
                if "tiktok" in identifier:
                    integration_id = it.get("id")
                    break
            if not integration_id and integrations:
                integration_id = integrations[0].get("id")

        if not integration_id:
            return PublicationResult(
                success=False,
                error="Aucun canal TikTok connecté trouvé dans Postiz. Connectez TikTok dans Postiz > Integrations.",
            )

        # 5. Préparation du post Postiz
        full_content = f"{post.title.strip()}\n\n{post.description}".strip()
        is_scheduled = bool(post.scheduled_at)
        sched_iso = (
            post.scheduled_at.astimezone(timezone.utc).isoformat()
            if is_scheduled and post.scheduled_at
            else None
        )

        body: dict[str, Any] = {
            "type": "schedule" if is_scheduled else "now",
            "date": sched_iso,
            "posts": [
                {
                    "integration": {
                        "id": integration_id,
                    },
                    "value": [
                        {
                            "content": full_content,
                            "media": [media_id],
                        }
                    ],
                    "settings": {
                        "__type": "tiktok",
                        "privacy_level": "PUBLIC_TO_EVERYONE" if post.privacy == "public" else "SELF_ONLY",
                    },
                }
            ],
        }

        # 6. Appel de création de post
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = self.get_auth_headers()
            try:
                res = await client.post(f"{self.base_url}/posts", headers=headers, json=body)
                if res.status_code not in (200, 201):
                    return PublicationResult(
                        success=False,
                        error=f"Erreur API Postiz ({res.status_code}): {res.text}",
                    )
                data = res.json()
                post_id = data.get("id") or (data.get("posts", [{}])[0].get("id") if "posts" in data else "postiz_created")
                return PublicationResult(
                    success=True,
                    external_id=str(post_id),
                    url=f"{self.raw_root_url}/posts/{post_id}",
                )
            except Exception as exc:
                return PublicationResult(success=False, error=f"Impossible de contacter Postiz: {exc}")

    async def status(self, tokens: dict[str, Any], external_id: str) -> PublicationStatusResult:
        if not self.is_enabled():
            return PublicationStatusResult(status="failed", external_id=external_id, error="Postiz non configuré")
        return PublicationStatusResult(status="published", external_id=external_id)
