from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt, encrypt
from app.core.security import generate_bearer_token, require_user, utcnow
from app.db.models import Setting
from app.db.session import get_db

router = APIRouter(prefix="/api/token", tags=["token"])

TOKEN_KEY = "sse_bearer_token"


async def _read_token(db: AsyncSession) -> str:
    row = await db.get(Setting, TOKEN_KEY)
    if row is None:
        raise HTTPException(status_code=500, detail="bearer token not initialized")
    return decrypt(row.value)


@router.get("")
async def get_token(db: AsyncSession = Depends(get_db), _uid: int = Depends(require_user)):
    row = await db.get(Setting, TOKEN_KEY)
    if row is None:
        raise HTTPException(status_code=500, detail="bearer token not initialized")
    return {"token": decrypt(row.value), "rotated_at": row.updated_at.isoformat()}


@router.post("/rotate")
async def rotate_token(request: Request, db: AsyncSession = Depends(get_db), _uid: int = Depends(require_user)):
    row = await db.get(Setting, TOKEN_KEY)
    new_token = generate_bearer_token()
    if row is None:
        row = Setting(key=TOKEN_KEY, value=encrypt(new_token), updated_at=utcnow())
        db.add(row)
    else:
        row.value = encrypt(new_token)
        row.updated_at = utcnow()
    await db.commit()
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is not None:
        await orch.restart_proxy()
    return {"token": new_token, "rotated_at": row.updated_at.isoformat()}
