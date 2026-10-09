from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import settings
from ..db import get_session
from ..models import Account, AccountOut
from ..publishing.crypto import decrypt_tokens, encrypt_tokens
from ..publishing.tiktok import TikTokPublisher
from ..publishing.youtube import YouTubePublisher

router = APIRouter(prefix="/accounts", tags=["accounts"])


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str = "http://localhost:3000/accounts/callback"


@router.get("", response_model=list[AccountOut])
def list_accounts(session: Session = Depends(get_session)) -> list[AccountOut]:
    """Liste des comptes connectés sans jamais exposer les jetons bruts."""
    accounts = session.exec(select(Account).order_by(Account.created_at.desc())).all()
    out = []
    now_utc = datetime.now(timezone.utc)

    for acc in accounts:
        # Vérifier si le jeton expire bientôt (< 10 minutes)
        current_status = acc.status
        if acc.expires_at:
            # S'assurer que expires_at a un fuseau timezone
            exp = acc.expires_at if acc.expires_at.tzinfo else acc.expires_at.replace(tzinfo=timezone.utc)
            if exp < now_utc:
                current_status = "needs_reconnect"
            elif exp < now_utc + timedelta(minutes=10):
                current_status = "expiring_soon"

        if current_status != acc.status:
            acc.status = current_status
            session.add(acc)
            session.commit()

        out.append(
            AccountOut(
                id=acc.id,
                platform=acc.platform,
                platform_account_id=acc.platform_account_id,
                name=acc.name,
                avatar_url=acc.avatar_url,
                expires_at=acc.expires_at,
                status=acc.status,
                created_at=acc.created_at,
            )
        )
    return out


@router.get("/postiz/status")
async def get_postiz_status() -> dict[str, Any]:
    """Interroge l'état de la connexion avec le service Postiz."""
    from ..publishing.postiz import PostizPublisher
    publisher = PostizPublisher()
    return await publisher.check_health()


@router.post("/postiz/sync", response_model=list[AccountOut])
async def sync_postiz_accounts(session: Session = Depends(get_session)) -> list[AccountOut]:
    """Synchronise les canaux connectés dans Postiz (TikTok, Instagram...) vers ClipFarm."""
    from ..publishing.postiz import PostizPublisher
    publisher = PostizPublisher()
    if not publisher.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="Postiz n'est pas configuré. Veuillez renseigner POSTIZ_API_KEY dans le fichier .env.",
        )

    integrations = await publisher.list_integrations()
    if not integrations:
        return []

    synced: list[AccountOut] = []
    now_utc = datetime.now(timezone.utc)

    for item in integrations:
        raw_platform = (item.get("identifier") or item.get("provider") or "tiktok").lower()
        # Normalisation de la plateforme
        if "tiktok" in raw_platform:
            platform = "tiktok"
        elif "instagram" in raw_platform or "reels" in raw_platform:
            platform = "instagram"
        elif "youtube" in raw_platform:
            platform = "youtube"
        else:
            platform = raw_platform

        item_id = str(item.get("id"))
        acc_id = f"postiz_{platform}_{item_id}"
        account_name = item.get("name") or item.get("username") or f"{platform.capitalize()} ({item_id[:6]})"
        avatar = item.get("picture") or item.get("avatar")

        tokens_data = {
            "integration_id": item_id,
            "platform": platform,
            "provider": raw_platform,
            "source": "postiz",
        }
        encrypted = encrypt_tokens(tokens_data)

        existing = session.get(Account, acc_id)
        if existing:
            existing.name = account_name
            existing.avatar_url = avatar
            existing.encrypted_tokens = encrypted
            existing.status = "connected"
            existing.updated_at = now_utc
            session.add(existing)
            session.commit()
            session.refresh(existing)
            acc = existing
        else:
            acc = Account(
                id=acc_id,
                platform=platform,
                platform_account_id=item_id,
                name=account_name,
                avatar_url=avatar,
                encrypted_tokens=encrypted,
                status="connected",
                created_at=now_utc,
            )
            session.add(acc)
            session.commit()
            session.refresh(acc)

        synced.append(
            AccountOut(
                id=acc.id,
                platform=acc.platform,
                platform_account_id=acc.platform_account_id,
                name=acc.name,
                avatar_url=acc.avatar_url,
                expires_at=acc.expires_at,
                status=acc.status,
                created_at=acc.created_at,
            )
        )

    return synced


@router.get("/connect/youtube")
def get_youtube_auth_url(
    redirect_uri: str = Query("http://localhost:3000/accounts/callback"),
) -> dict[str, str]:
    """Génère l'URL d'autorisation Google OAuth pour YouTube."""
    publisher = YouTubePublisher()
    try:
        url = publisher.get_auth_url(redirect_uri=redirect_uri)
        return {"auth_url": url, "platform": "youtube"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/connect/youtube/callback", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def youtube_oauth_callback(
    req: OAuthCallbackRequest,
    session: Session = Depends(get_session),
) -> AccountOut:
    """Échange le code OAuth, chiffre les jetons et enregistre le compte."""
    publisher = YouTubePublisher()
    try:
        info = await publisher.connect(code=req.code, redirect_uri=req.redirect_uri)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Échec de connexion YouTube : {exc}")

    acc_id = f"yt_{info.platform_account_id}"
    encrypted_toks = encrypt_tokens(info.tokens)

    existing = session.get(Account, acc_id)
    if existing:
        existing.name = info.name
        existing.avatar_url = info.avatar_url
        existing.encrypted_tokens = encrypted_toks
        existing.expires_at = info.expires_at
        existing.status = "connected"
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        acc = existing
    else:
        acc = Account(
            id=acc_id,
            platform="youtube",
            platform_account_id=info.platform_account_id,
            name=info.name,
            avatar_url=info.avatar_url,
            encrypted_tokens=encrypted_toks,
            expires_at=info.expires_at,
            status="connected",
        )
        session.add(acc)
        session.commit()
        session.refresh(acc)

    return AccountOut(
        id=acc.id,
        platform=acc.platform,
        platform_account_id=acc.platform_account_id,
        name=acc.name,
        avatar_url=acc.avatar_url,
        expires_at=acc.expires_at,
        status=acc.status,
        created_at=acc.created_at,
    )


@router.get("/connect/tiktok")
def get_tiktok_auth_url(
    redirect_uri: str = Query("http://localhost:3000/accounts/callback"),
) -> dict[str, str]:
    """Génère l'URL d'autorisation TikTok OAuth."""
    publisher = TikTokPublisher()
    try:
        url = publisher.get_auth_url(redirect_uri=redirect_uri)
        return {"auth_url": url, "platform": "tiktok"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/connect/tiktok/callback", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def tiktok_oauth_callback(
    req: OAuthCallbackRequest,
    session: Session = Depends(get_session),
) -> AccountOut:
    """Échange le code OAuth, chiffre les jetons et enregistre le compte TikTok."""
    publisher = TikTokPublisher()
    try:
        info = await publisher.connect(code=req.code, redirect_uri=req.redirect_uri)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Échec de connexion TikTok : {exc}")

    acc_id = f"tt_{info.platform_account_id}"
    encrypted_toks = encrypt_tokens(info.tokens)

    existing = session.get(Account, acc_id)
    if existing:
        existing.name = info.name
        existing.avatar_url = info.avatar_url
        existing.encrypted_tokens = encrypted_toks
        existing.expires_at = info.expires_at
        existing.status = "connected"
        existing.updated_at = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        acc = existing
    else:
        acc = Account(
            id=acc_id,
            platform="tiktok",
            platform_account_id=info.platform_account_id,
            name=info.name,
            avatar_url=info.avatar_url,
            encrypted_tokens=encrypted_toks,
            expires_at=info.expires_at,
            status="connected",
        )
        session.add(acc)
        session.commit()
        session.refresh(acc)

    return AccountOut(
        id=acc.id,
        platform=acc.platform,
        platform_account_id=acc.platform_account_id,
        name=acc.name,
        avatar_url=acc.avatar_url,
        expires_at=acc.expires_at,
        status=acc.status,
        created_at=acc.created_at,
    )


@router.delete("/{id}")
def delete_account(id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Déconnecte un compte et supprime définitivement ses jetons chiffrés."""
    acc = session.get(Account, id)
    if not acc:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    session.delete(acc)
    session.commit()
    return {"ok": True, "message": f"Compte {acc.name} déconnecté et jetons supprimés."}


@router.post("/test-account", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_test_account(
    platform: str = Query("youtube"),
    name: str = Query("ClipFarm Studio (Démo)"),
    session: Session = Depends(get_session),
) -> AccountOut:
    """Crée un compte de test local pour faciliter les vérifications et le développement."""
    import uuid

    acc_id = f"{platform}_test_{uuid.uuid4().hex[:6]}"
    tokens = {
        "access_token": "mock_access_token_dev",
        "refresh_token": "mock_refresh_token_dev",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }
    acc = Account(
        id=acc_id,
        platform=platform,
        platform_account_id=f"UC_{uuid.uuid4().hex[:8]}",
        name=name,
        avatar_url=None,
        encrypted_tokens=encrypt_tokens(tokens),
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        status="connected",
    )
    session.add(acc)
    session.commit()
    session.refresh(acc)

    return AccountOut(
        id=acc.id,
        platform=acc.platform,
        platform_account_id=acc.platform_account_id,
        name=acc.name,
        avatar_url=acc.avatar_url,
        expires_at=acc.expires_at,
        status=acc.status,
        created_at=acc.created_at,
    )
