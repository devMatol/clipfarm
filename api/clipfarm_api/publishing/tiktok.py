from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

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
from .sanitizer import check_video_for_platform, sanitize_video_for_publishing

logger = logging.getLogger("clipfarm_api.tiktok")


class TikTokPublisher(Publisher):
    """
    Adaptateur officiel TikTok Content Posting API (Direct Post).
    100% Gratuit, direct et sans intermédiaire. Utilise les identifiants gratuits
    TikTok for Developers (Client Key & Client Secret).
    """

    OAUTH_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
    OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    API_BASE = "https://open.tiktokapis.com/v2"

    SCOPES: ClassVar[list[str]] = [
        "user.info.basic",
        "video.upload",
        "video.publish",
    ]

    def __init__(
        self,
        client_key: str | None = None,
        client_secret: str | None = None,
    ):
        self.client_key = client_key or settings.tiktok_client_key
        self.client_secret = client_secret or settings.tiktok_client_secret

    def is_configured(self) -> bool:
        return bool(self.client_key and self.client_secret)

    def get_auth_url(self, redirect_uri: str, state: str = "tiktok_auth") -> str:
        """Génère l'URL officielle de connexion TikTok OAuth 2.0."""
        if not self.client_key:
            raise ValueError(
                "TIKTOK_CLIENT_KEY non configuré dans .env. "
                "Créez une application gratuite sur https://developers.tiktok.com."
            )

        params = {
            "client_key": self.client_key,
            "scope": ",".join(self.SCOPES),
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return str(httpx.URL(self.OAUTH_AUTH_URL, params=params))

    async def connect(self, code: str, redirect_uri: str, **kwargs) -> AccountInfo:
        """Échange le code OAuth contre les jetons d'accès et récupère le nom/avatar du profil TikTok."""
        if not self.client_key or not self.client_secret:
            raise ValueError("TIKTOK_CLIENT_KEY ou TIKTOK_CLIENT_SECRET manquant.")

        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                self.OAUTH_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=data,
            )
            if res.status_code != 200:
                raise RuntimeError(f"Échec de l'authentification TikTok ({res.status_code}): {res.text}")

            token_data = res.json().get("data", {})
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            open_id = token_data.get("open_id") or "tiktok_user"
            expires_in = token_data.get("expires_in", 86400)

            if not access_token:
                raise RuntimeError(f"TikTok n'a pas retourné d'access_token: {res.text}")

            # Récupération du profil public
            user_res = await client.get(
                f"{self.API_BASE}/user/info/?fields=open_id,display_name,avatar_url",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            display_name = f"TikTok User ({open_id[:8]})"
            avatar_url = None

            if user_res.status_code == 200:
                user_info = user_res.json().get("data", {}).get("user", {})
                display_name = user_info.get("display_name") or display_name
                avatar_url = user_info.get("avatar_url")

            tokens = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "open_id": open_id,
            }

            return AccountInfo(
                platform_account_id=open_id,
                name=display_name,
                avatar_url=avatar_url,
                tokens=tokens,
                expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            )

    async def refresh_token(self, tokens: dict[str, Any]) -> dict[str, Any]:
        """Rafraîchit l'access_token TikTok si expiré."""
        refresh_tok = tokens.get("refresh_token")
        if not refresh_tok or not self.client_key or not self.client_secret:
            return tokens

        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(
                    self.OAUTH_TOKEN_URL,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data=data,
                )
                if res.status_code == 200:
                    token_data = res.json().get("data", {})
                    tokens["access_token"] = token_data.get("access_token", tokens["access_token"])
                    tokens["refresh_token"] = token_data.get("refresh_token", refresh_tok)
            except (httpx.HTTPError, KeyError) as exc:
                logger.warning("Échec du rafraîchissement du jeton TikTok: %s", exc)

        return tokens

    def validate(self, post: PublicationPayload, video_path: Path | None = None) -> ValidationResult:
        errors = []
        warnings = []

        if not post.title:
            errors.append("Le titre de la vidéo TikTok est obligatoire.")

        # Limite TikTok : titre/légende max 2200 caractères
        full_text = f"{post.title} {post.description}".strip()
        if len(full_text) > 2200:
            errors.append(f"Le texte du TikTok dépasse la limite autorisée de 2200 caractères ({len(full_text)} car.).")

        # Vérification format vidéo
        if video_path and video_path.exists():
            valid_vid, vid_errs = check_video_for_platform(video_path, max_duration_s=600.0, allow_square=True)
            if not valid_vid:
                errors.extend(vid_errs)

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    async def upload(self, tokens: dict[str, Any], post: PublicationPayload, video_path: Path) -> PublicationResult:
        """Envoie la vidéo directement sur TikTok via l'API officielle FILE_UPLOAD."""
        # 1. Mode test / mock local immédiat
        if tokens.get("access_token") == "mock_access_token_dev" or tokens.get("is_mock"):
            import uuid
            mock_id = f"tt_mock_{uuid.uuid4().hex[:8]}"
            return PublicationResult(
                success=True,
                external_id=mock_id,
                url=f"https://www.tiktok.com/@clipfarm_demo/video/{uuid.uuid4().int % 10000000000}",
            )

        tokens = await self.refresh_token(tokens)
        access_token = tokens.get("access_token")
        if not access_token:
            return PublicationResult(success=False, error="Jeton d'accès TikTok manquant ou invalide.")

        # 2. Nettoyage métadonnées (suppression GPS)
        sanitized_dir = video_path.parent / "sanitized"
        sanitized_dir.mkdir(parents=True, exist_ok=True)
        target_clean = sanitized_dir / f"clean_{video_path.name}"
        clean_video = sanitize_video_for_publishing(video_path, target_clean)

        file_size = clean_video.stat().st_size
        video_bytes = clean_video.read_bytes()

        # 3. Préparation du post info
        # Les applications non auditées doivent être publiées en SELF_ONLY (privé)
        privacy_level = "PUBLIC_TO_EVERYONE" if post.privacy == "public" else "SELF_ONLY"
        title_content = f"{post.title.strip()}\n\n{post.description}".strip()[:2200]

        init_body = {
            "post_info": {
                "title": title_content,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_stitch": False,
                "disable_comment": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            # Initialisation de la publication
            init_res = await client.post(
                f"{self.API_BASE}/post/publish/video/init/",
                headers=headers,
                json=init_body,
            )

            if init_res.status_code != 200:
                return PublicationResult(
                    success=False,
                    error=f"Erreur initialisation TikTok ({init_res.status_code}): {init_res.text}",
                )

            init_data = init_res.json().get("data", {})
            publish_id = init_data.get("publish_id")
            upload_url = init_data.get("upload_url")

            if not upload_url:
                return PublicationResult(
                    success=False,
                    error=f"TikTok n'a pas retourné d'URL d'upload: {init_res.text}",
                )

            # Upload du binaire vidéo vers l'URL fournie par TikTok

            upload_headers = {
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
            }

            put_res = await client.put(upload_url, headers=upload_headers, content=video_bytes)
            if put_res.status_code not in (200, 201, 204):
                return PublicationResult(
                    success=False,
                    error=f"Échec téléversement vidéo TikTok ({put_res.status_code}): {put_res.text}",
                )

            return PublicationResult(
                success=True,
                external_id=str(publish_id),
                url="https://www.tiktok.com",
            )

    async def status(self, tokens: dict[str, Any], external_id: str) -> PublicationStatusResult:
        return PublicationStatusResult(status="published", external_id=external_id)
