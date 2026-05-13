from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_user
from app.manifest.loader import load_manifest

router = APIRouter(prefix="/api", tags=["manifest"])


@router.get("/manifest")
async def get_manifest(_uid: int = Depends(require_user)):
    return load_manifest().model_dump()
