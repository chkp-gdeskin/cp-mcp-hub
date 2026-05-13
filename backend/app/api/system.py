from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.db.session import get_db
from app.manifest.loader import load_manifest

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def health(request: Request, db: AsyncSession = Depends(get_db)):
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    orch = getattr(request.app.state, "orchestrator", None)
    proxy_state = orch.proxy_state() if orch else "stopped"
    overall = "ok" if db_ok and proxy_state in {"running", "stopped"} else "degraded"
    return {
        "status": overall,
        "db": "ok" if db_ok else "error",
        "mcp_proxy": proxy_state,
    }


@router.get("/info")
async def info():
    m = load_manifest()
    return {
        "version": __version__,
        "manifest_version": m.version,
        "manifest_generated_at": m.generated_at,
        "manifest_source_commit": m.source_commit,
        "server_count": len(m.servers),
    }
