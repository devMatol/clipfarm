from __future__ import annotations

import base64
import json
import os
from typing import Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config import settings


def _get_fernet_key() -> bytes:
    """Récupère ou dérive une clé Fernet 32 octets base64 depuis settings.secret_key."""
    raw_key = settings.secret_key.strip()
    if not raw_key:
        # Clé de repli locale déterministe basée sur l'environnement pour éviter tout plantage en dev
        raw_key = "clipfarm_local_development_secret_key_change_in_prod"

    # Si la clé est déjà au format Fernet valide (32 octets base64 url-safe)
    try:
        decoded = base64.urlsafe_b64decode(raw_key.encode("utf-8"))
        if len(decoded) == 32:
            return raw_key.encode("utf-8")
    except Exception:
        pass

    # Dérivation sécurisée PBKDF2 vers 32 octets Fernet
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"clipfarm_salt_publishing_v1",
        iterations=100_000,
    )
    derived = kdf.derive(raw_key.encode("utf-8"))
    return base64.urlsafe_b64encode(derived)


def encrypt_tokens(data: dict[str, Any]) -> str:
    """Chiffre les jetons sous forme de chaîne chiffrée Fernet."""
    f = Fernet(_get_fernet_key())
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return f.encrypt(payload).decode("utf-8")


def decrypt_tokens(ciphertext: str) -> dict[str, Any]:
    """Déchiffre les jetons depuis la chaîne chiffrée Fernet."""
    if not ciphertext:
        return {}
    f = Fernet(_get_fernet_key())
    decrypted = f.decrypt(ciphertext.encode("utf-8"))
    return json.loads(decrypted.decode("utf-8"))
