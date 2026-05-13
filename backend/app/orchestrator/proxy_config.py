from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.servers import decrypt_config_for_runtime
from app.db.models import ServerState
from app.manifest.loader import get_server_def, load_manifest


def _resolve_npx() -> str:
    """Find npx; prefer the system one. Falls back to "npx" and relies on PATH."""
    return shutil.which("npx") or "npx"


async def build_named_servers_config(db: AsyncSession) -> dict[str, Any]:
    """Build the mcp-proxy named-servers config from enabled ServerState rows."""
    rows = (await db.execute(select(ServerState).where(ServerState.enabled.is_(True)))).scalars().all()
    manifest_ids = {s.id for s in load_manifest().servers}
    npx = _resolve_npx()
    servers: dict[str, dict[str, Any]] = {}
    for state in rows:
        if state.id not in manifest_ids:
            continue
        defn = get_server_def(state.id)
        if not defn:
            continue
        env = decrypt_config_for_runtime(state, defn)
        if not state.telemetry_enabled:
            env["TELEMETRY_DISABLED"] = "true"
        servers[state.id] = {
            "command": npx,
            "args": ["-y", defn.npm_package, *list(state.cli_args or [])],
            "env": env,
            "transportType": "stdio",
        }
    return {"mcpServers": servers}


def write_proxy_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
