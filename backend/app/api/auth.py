from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    SESSION_COOKIE,
    SESSION_TTL,
    hash_password,
    make_session_token,
    require_user,
    utcnow,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=12)


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    is_https = request.headers.get("x-forwarded-proto", "").lower() == "https"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=is_https,
        path="/",
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    user.last_login_at = utcnow()
    await db.commit()
    _set_session_cookie(response, request, make_session_token(user.id))
    return {"username": user.username, "must_change_password": user.must_change_password}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    uid: int = Depends(require_user),
):
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="old password is incorrect")
    if body.old_password == body.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new password must differ from old")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await db.commit()
    _set_session_cookie(response, request, make_session_token(user.id))
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(uid: int = Depends(require_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    return {"username": user.username, "must_change_password": user.must_change_password}
