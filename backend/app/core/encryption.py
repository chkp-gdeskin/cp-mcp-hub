from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.settings import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().MASTER_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


@lru_cache
def derived_secret_key() -> bytes:
    """HKDF-derive a session-signing key from MASTER_KEY when SECRET_KEY is not set."""
    settings = get_settings()
    if settings.SECRET_KEY:
        return settings.SECRET_KEY.encode()
    master = base64.urlsafe_b64decode(settings.MASTER_KEY)
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"cp-mcp-hub", info=b"session-cookie")
    return hkdf.derive(master)
