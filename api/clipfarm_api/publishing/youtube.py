from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
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
from .sanitizer import check_video_for_platform, sanitize_video_for_publishing


class YouTubePublisher(Publisher):
    """Adaptateur YouTube Data API v3 pour la publication sécurisée de YouTube Shorts."""

    OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE = "https://www.googleapis.com/youtube/v3"
    UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3"

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.client_id = client_id or settings.youtube_client_id or "clipfarm_client_id"
        self.client_secret = client_secret or settings.youtube_client_secret or "clipfarm_client_secret"

    def get_auth_url(self, redirect_uri: str, state: str = "") -> str:
        """Génère l'URL d'autorisation OAuth 2.0 pour compte Google/YouTube."""
        if not self.client_id:
            raise ValueError("YOUTUBE_CLIENT_ID non configuré.")

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return str(httpx.URL(self.OAUTH_AUTH_URL, params=params))

    async def connect(self, code: str, redirect_uri: str, **kwargs) -> AccountInfo:
        """Échange le code d'autorisation contre des jetons et récupère le nom/avatar de la chaîne."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Identifiants OAuth YouTube manquants (YOUTUBE_CLIENT_ID et YOUTUBE_CLIENT_SECRET).")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Échange du code d'autorisation
            token_res = await client.post(
                self.OAUTH_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )

            if token_res.status_code != 200:
                err_text = token_res.text
                raise RuntimeError(f"Échec de l'échange OAuth Google ({token_res.status_code}): {err_text}")

            token_data = token_res.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # 2. Récupération des informations de la chaîne YouTube
            channel_res = await client.get(
                f"{self.API_BASE}/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if channel_res.status_code != 200:
                raise RuntimeError(f"Impossible de récupérer la chaîne YouTube ({channel_res.status_code}): {channel_res.text}")

            ch_json = channel_res.json()
            items = ch_json.get("items", [])
            if not items:
                raise RuntimeError("Aucune chaîne YouTube trouvée pour ce compte Google.")

            ch_item = items[0]
            channel_id = ch_item["id"]
            snippet = ch_item.get("snippet", {})
            title = snippet.get("title", f"Chaîne {channel_id}")
            avatar_url = snippet.get("thumbnails", {}).get("default", {}).get("url")

            return AccountInfo(
                platform_account_id=channel_id,
                name=title,
                avatar_url=avatar_url,
                tokens=token_data,
                expires_at=expires_at,
            )

    async def refresh_token(self, tokens: dict[str, Any]) -> dict[str, Any]:
        """Rafraîchit l'access_token si un refresh_token est présent et que le jeton est expiré ou proche de l'expiration."""
        refresh_tok = tokens.get("refresh_token")
        if not refresh_tok:
            return tokens

        expires_at_str = tokens.get("expires_at")
        if expires_at_str and tokens.get("access_token"):
            try:
                exp_dt = datetime.fromisoformat(expires_at_str)
                # Si le jeton est encore valide plus de 5 minutes, pas besoin de rafraîchir
                if exp_dt > datetime.now(timezone.utc) + timedelta(minutes=5):
                    return tokens
            except Exception:
                pass

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                self.OAUTH_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_tok,
                    "grant_type": "refresh_token",
                },
            )
            if res.status_code == 200:
                try:
                    new_data = res.json()
                    if "access_token" in new_data:
                        tokens["access_token"] = new_data["access_token"]
                    if "expires_in" in new_data:
                        tokens["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=new_data["expires_in"])).isoformat()
                except Exception:
                    pass
            return tokens

    def validate(self, post: PublicationPayload, video_path: Optional[Path] = None) -> ValidationResult:
        """Validation stricte des contraintes YouTube Shorts avant envoi."""
        errors: list[str] = []
        warnings: list[str] = []

        # Titre obligatoire (1 à 100 caractères)
        title = post.title.strip()
        if not title:
            errors.append("Le titre de la vidéo est obligatoire.")
        elif len(title) > 100:
            errors.append(f"Le titre dépasse 100 caractères ({len(title)} caractères).")

        # Description (max 5000 caractères)
        if len(post.description) > 5000:
            errors.append(f"La description dépasse 5 000 caractères ({len(post.description)} caractères).")

        # Tags (max 500 caractères cumulés)
        combined_tags_len = sum(len(t) for t in post.tags)
        if combined_tags_len > 500:
            errors.append(f"Les tags combinés dépassent 500 caractères ({combined_tags_len} caractères).")

        # Confidentialité
        if post.privacy not in ("private", "unlisted", "public"):
            errors.append("La visibilité doit être 'private', 'unlisted' ou 'public'.")

        # Planification native YouTube
        if post.scheduled_at:
            now_utc = datetime.now(timezone.utc)
            if post.scheduled_at <= now_utc + timedelta(minutes=5):
                errors.append("La date de programmation doit être située au moins 5 minutes dans le futur.")
            if post.privacy != "private":
                warnings.append("YouTube impose le mode 'private' lors d'une programmation avec publishAt (appliqué automatiquement).")

        # Hashtag #Shorts
        if "#Shorts" not in title and "#Shorts" not in post.description and "#shorts" not in title and "#shorts" not in post.description:
            warnings.append("Il est vivement conseillé d'inclure le tag #Shorts dans le titre ou la description pour l'algorithme YouTube.")

        # Vérification technique du fichier vidéo
        if video_path and video_path.exists():
            valid_vid, vid_errs = check_video_for_platform(video_path, max_duration_s=180.0, allow_square=True)
            if not valid_vid:
                errors.extend(vid_errs)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def upload(self, tokens: dict[str, Any], post: PublicationPayload, video_path: Path) -> PublicationResult:
        """Envoie la vidéo à YouTube via le protocole d'upload résumable."""
        tokens = await self.refresh_token(tokens)
        access_token = tokens.get("access_token")
        if not access_token:
            return PublicationResult(success=False, error="Jeton d'accès YouTube manquant ou expiré.")

        # 1. Nettoyage strict des métadonnées vidéo (suppression GPS, auteur, etc.)
        sanitized_dir = video_path.parent / "sanitized"
        sanitized_dir.mkdir(parents=True, exist_ok=True)
        target_clean = sanitized_dir / f"clean_{video_path.name}"
        sanitized_video = sanitize_video_for_publishing(video_path, target_clean)

        # Préparation du titre (ajouter #Shorts si pas présent et place restante)
        final_title = post.title.strip()
        if "#Shorts" not in final_title and "#shorts" not in final_title:
            if len(final_title) + 8 <= 100:
                final_title = f"{final_title} #Shorts"

        # 2. Métadonnées JSON
        snippet: dict[str, Any] = {
            "title": final_title[:100],
            "description": post.description,
            "tags": post.tags[:30],
            "categoryId": post.category_id or "22",
        }

        status: dict[str, Any] = {
            "privacyStatus": post.privacy if not post.scheduled_at else "private",
            "selfDeclaredMadeForKids": bool(post.made_for_kids),
        }

        if post.scheduled_at:
            # publishAt impose privacyStatus = private
            status["publishAt"] = post.scheduled_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        metadata_body = {
            "snippet": snippet,
            "status": status,
        }

        file_size = sanitized_video.stat().st_size

        async with httpx.AsyncClient(timeout=120.0) as client:
            # 3. Initialisation de la session d'upload résumable
            init_res = await client.post(
                f"{self.UPLOAD_BASE}/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Length": str(file_size),
                    "X-Upload-Content-Type": "video/mp4",
                },
                content=json.dumps(metadata_body),
            )

            if init_res.status_code not in (200, 201):
                err_text = init_res.text
                if "quotaExceeded" in err_text:
                    return PublicationResult(success=False, error="Quota YouTube dépassé pour aujourd'hui (1600 unités consommées par upload).")
                return PublicationResult(success=False, error=f"Échec initialisation upload YouTube ({init_res.status_code}): {err_text}")

            upload_url = init_res.headers.get("Location")
            if not upload_url:
                return PublicationResult(success=False, error="YouTube n'a pas retourné d'URL d'upload résumable.")

            # 4. Envoi du fichier vidéo
            with open(sanitized_video, "rb") as vf:
                video_bytes = vf.read()

            upload_res = await client.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size),
                },
                content=video_bytes,
            )

            if upload_res.status_code not in (200, 201):
                return PublicationResult(success=False, error=f"Échec transmission vidéo YouTube ({upload_res.status_code}): {upload_res.text}")

            res_json = upload_res.json()
            video_id = res_json.get("id")
            if not video_id:
                return PublicationResult(success=False, error="ID vidéo non retourné par YouTube.")

            short_url = f"https://youtube.com/shorts/{video_id}"

            # 5. Miniature optionnelle si fournie
            if post.cover_image_path and post.cover_image_path.exists():
                try:
                    with open(post.cover_image_path, "rb") as cf:
                        cover_bytes = cf.read()
                    await client.post(
                        f"{self.UPLOAD_BASE}/thumbnails/set",
                        params={"videoId": video_id},
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "image/jpeg",
                        },
                        content=cover_bytes,
                    )
                except Exception as thumb_exc:
                    print(f"[youtube] Échec envoi miniature (facultatif): {thumb_exc}")

            return PublicationResult(
                success=True,
                external_id=video_id,
                url=short_url,
                status="published",
            )

    async def status(self, tokens: dict[str, Any], external_id: str) -> PublicationStatusResult:
        """Interroge le statut de traitement d'un Short sur YouTube."""
        tokens = await self.refresh_token(tokens)
        access_token = tokens.get("access_token")
        if not access_token:
            return PublicationStatusResult(status="failed", external_id=external_id, error="Jeton manquant")

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(
                f"{self.API_BASE}/videos",
                params={"part": "status,snippet", "id": external_id},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if res.status_code != 200:
                return PublicationStatusResult(status="failed", external_id=external_id, error=f"Erreur API ({res.status_code}): {res.text}")

            items = res.json().get("items", [])
            if not items:
                return PublicationStatusResult(status="failed", external_id=external_id, error="Vidéo introuvable sur YouTube")

            v_status = items[0].get("status", {})
            upload_status = v_status.get("uploadStatus", "uploaded")
            failure_reason = v_status.get("failureReason")
            rejection_reason = v_status.get("rejectionReason")

            if upload_status == "failed" or failure_reason or rejection_reason:
                return PublicationStatusResult(
                    status="failed",
                    external_id=external_id,
                    error=f"Rejet YouTube: {failure_reason or rejection_reason or 'Upload failed'}",
                )

            mapped_status = "published" if upload_status in ("processed", "uploaded") else "processing"
            return PublicationStatusResult(
                status=mapped_status,
                external_id=external_id,
                url=f"https://youtube.com/shorts/{external_id}",
            )
