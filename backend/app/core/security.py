from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from app.core.encryption import derived_secret_key

SESSION_COOKIE = "cpmcp_session"
SESSION_TTL = timedelta(days=7)


def _signer() -> TimestampSigner:
    return TimestampSigner(derived_secret_key())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def make_session_token(user_id: int) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = f"{user_id}.{nonce}"
    return _signer().sign(payload.encode()).decode()


def read_session(request: Request) -> int | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    try:
        payload = _signer().unsign(raw.encode(), max_age=int(SESSION_TTL.total_seconds())).decode()
        user_id_str, _ = payload.split(".", 1)
        return int(user_id_str)
    except (BadSignature, SignatureExpired, ValueError):
        return None


def require_user(request: Request) -> int:
    uid = read_session(request)
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    return uid


def generate_bearer_token() -> str:
    return secrets.token_urlsafe(48)


def utcnow() -> datetime:
    return datetime.now(UTC)
