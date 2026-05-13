from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt, encrypt
from app.core.security import require_user, utcnow
from app.db.models import ServerState
from app.db.session import get_db
from app.manifest.loader import get_server_def, load_manifest

router = APIRouter(prefix="/api/servers", tags=["servers"])

SECRET_PLACEHOLDER = "********"


class ServerConfigUpdate(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    cli_args: list[str] = Field(default_factory=list)
    telemetry_enabled: bool = False
    restart_policy: Literal["always", "on-failure", "never"] = "on-failure"


def _public_config(state: ServerState) -> dict[str, Any]:
    """Return config with secret values replaced by sentinel."""
    defn = get_server_def(state.id)
    secret_names = {ev.name for ev in defn.env_vars if ev.secret} if defn else set()
    out: dict[str, Any] = {}
    for k, v in (state.config or {}).items():
        if k in secret_names and v:
            out[k] = SECRET_PLACEHOLDER
        else:
            out[k] = v
    return out


async def _runtime_status(request: Request, server_id: str) -> dict[str, Any]:
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        return {"state": "unknown"}
    return orch.runtime_status(server_id)


@router.get("")
async def list_servers(request: Request, db: AsyncSession = Depends(get_db), _uid: int = Depends(require_user)):
    rows = (await db.execute(select(ServerState))).scalars().all()
    by_id = {r.id: r for r in rows}
    items = []
    for defn in load_manifest().servers:
        s = by_id.get(defn.id)
        runtime = await _runtime_status(request, defn.id)
        items.append({
            "id": defn.id,
            "display_name": defn.display_name,
            "description": defn.description,
            "icon": defn.icon,
            "enabled": bool(s and s.enabled),
            "telemetry_enabled": bool(s and s.telemetry_enabled),
            "restart_policy": (s.restart_policy if s else "on-failure"),
            "last_error": s.last_error if s else None,
            "last_started_at": s.last_started_at.isoformat() if s and s.last_started_at else None,
            **runtime,
        })
    return {"servers": items}


@router.get("/{server_id}")
async def get_server(server_id: str, request: Request, db: AsyncSession = Depends(get_db), _uid: int = Depends(require_user)):
    defn = get_server_def(server_id)
    if not defn:
        raise HTTPException(status_code=404, detail="unknown server")
    state = await db.get(ServerState, server_id)
    if state is None:
        raise HTTPException(status_code=404, detail="server state not initialized")
    runtime = await _runtime_status(request, server_id)
    return {
        "id": defn.id,
        "display_name": defn.display_name,
        "description": defn.description,
        "doc_url": defn.doc_url,
        "icon": defn.icon,
        "definition": defn.model_dump(),
        "enabled": state.enabled,
        "config": _public_config(state),
        "cli_args": state.cli_args,
        "telemetry_enabled": state.telemetry_enabled,
        "restart_policy": state.restart_policy,
        "last_error": state.last_error,
        "last_started_at": state.last_started_at.isoformat() if state.last_started_at else None,
        **runtime,
    }


@router.put("/{server_id}/config")
async def update_config(
    server_id: str,
    body: ServerConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _uid: int = Depends(require_user),
):
    defn = get_server_def(server_id)
    if not defn:
        raise HTTPException(status_code=404, detail="unknown server")
    state = await db.get(ServerState, server_id)
    if state is None:
        raise HTTPException(status_code=404, detail="server state not initialized")

    env_def_by_name = {ev.name: ev for ev in defn.env_vars}
    existing = dict(state.config or {})
    new_config: dict[str, Any] = {}
    for key, value in body.config.items():
        if key not in env_def_by_name:
            # Allow extra env vars but treat as plain strings
            new_config[key] = "" if value is None else str(value)
            continue
        ev = env_def_by_name[key]
        if value is None or value == "":
            new_config[key] = ""
            continue
        if ev.secret:
            if value == SECRET_PLACEHOLDER:
                # Preserve existing encrypted value
                if key in existing:
                    new_config[key] = existing[key]
                continue
            new_config[key] = encrypt(str(value))
        else:
            new_config[key] = str(value) if not isinstance(value, (bool, int, float)) else value
    # Preserve any secrets that the client didn't send at all
    for key, val in existing.items():
        if key not in new_config and env_def_by_name.get(key) and env_def_by_name[key].secret:
            new_config[key] = val

    state.config = new_config
    state.cli_args = body.cli_args
    state.telemetry_enabled = body.telemetry_enabled
    state.restart_policy = body.restart_policy
    await db.commit()

    orch = getattr(request.app.state, "orchestrator", None)
    if orch is not None and state.enabled:
        await orch.request_reconcile()
    return {"ok": True}


@router.post("/{server_id}/enable")
async def enable_server(server_id: str, request: Request, db: AsyncSession = Depends(get_db), _uid: int = Depends(require_user)):
    defn = get_server_def(server_id)
    if not defn:
        raise HTTPException(status_code=404, detail="unknown server")
    state = await db.get(ServerState, server_id)
    if state is None:
        raise HTTPException(status_code=404, detail="server state not initialized")
    # Validate required env vars present
    missing = [
        ev.name for ev in defn.env_vars
        if ev.required and not (state.config or {}).get(ev.name)
    ]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"missing_required": missing})
    state.enabled = True
    state.last_started_at = utcnow()
    state.last_error = None
    await db.commit()
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is not None:
        await orch.request_reconcile()
    return {"ok": True}


@router.post("/{server_id}/disable")
async def disable_server(server_id: str, request: Request, db: AsyncSession = Depends(get_db), _uid: int = Depends(require_user)):
    state = await db.get(ServerState, server_id)
    if state is None:
        raise HTTPException(status_code=404, detail="server state not initialized")
    state.enabled = False
    await db.commit()
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is not None:
        await orch.request_reconcile()
    return {"ok": True}


@router.post("/{server_id}/restart")
async def restart_server(server_id: str, request: Request, db: AsyncSession = Depends(get_db), _uid: int = Depends(require_user)):
    state = await db.get(ServerState, server_id)
    if state is None or not state.enabled:
        raise HTTPException(status_code=400, detail="server is not enabled")
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is not None:
        await orch.restart_proxy()
    return {"ok": True}


@router.get("/{server_id}/config/reveal/{field_name}")
async def reveal_secret(
    server_id: str,
    field_name: str,
    db: AsyncSession = Depends(get_db),
    _uid: int = Depends(require_user),
):
    """Return the plaintext of a single stored secret field.

    Distinct from the regular GET /{server_id} which always masks secrets.
    Calling this requires an authenticated session. Designed for the
    admin's own UI to verify a saved value without re-entering it.
    """
    defn = get_server_def(server_id)
    if not defn:
        raise HTTPException(status_code=404, detail="unknown server")
    env_def = next((ev for ev in defn.env_vars if ev.name == field_name), None)
    if env_def is None or not env_def.secret:
        raise HTTPException(status_code=404, detail="unknown secret field")
    state = await db.get(ServerState, server_id)
    if state is None:
        raise HTTPException(status_code=404, detail="server state not initialized")
    stored = (state.config or {}).get(field_name)
    if not stored:
        # Field has no saved value; nothing to reveal
        return {"value": ""}
    try:
        plaintext = decrypt(stored)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="failed to decrypt field; MASTER_KEY may have changed") from exc
    return {"value": plaintext}


@router.get("/{server_id}/status")
async def server_status(server_id: str, request: Request, _uid: int = Depends(require_user)):
    defn = get_server_def(server_id)
    if not defn:
        raise HTTPException(status_code=404, detail="unknown server")
    runtime = await _runtime_status(request, server_id)
    settings_app = request.app
    base = getattr(settings_app.state, "external_base_url", "")
    sse_url = f"{base}/servers/{server_id}/sse" if base else f"/servers/{server_id}/sse"
    return {"id": server_id, "sse_url": sse_url, **runtime}


def decrypt_config_for_runtime(state: ServerState, defn) -> dict[str, str]:
    """Materialize plaintext env values for a server (used by orchestrator)."""
    secret_names = {ev.name for ev in defn.env_vars if ev.secret}
    out: dict[str, str] = {}
    for k, v in (state.config or {}).items():
        if not v:
            continue
        if k in secret_names:
            try:
                out[k] = decrypt(v) if isinstance(v, str) else str(v)
            except Exception:
                out[k] = ""
        else:
            out[k] = str(v)
    return out
