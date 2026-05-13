from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.security import require_user

router = APIRouter(prefix="/api/servers", tags=["logs"])


@router.get("/{server_id}/logs")
async def get_recent_logs(server_id: str, request: Request, lines: int = Query(200, ge=1, le=2000), _uid: int = Depends(require_user)):
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="orchestrator not ready")
    return {"lines": orch.recent_logs(server_id, lines)}


@router.get("/{server_id}/logs/stream")
async def stream_logs(server_id: str, request: Request, _uid: int = Depends(require_user)):
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="orchestrator not ready")

    queue = orch.subscribe(server_id)

    async def gen():
        try:
            # Replay last 100 lines as backfill
            for entry in orch.recent_logs(server_id, 100):
                yield f"data: {json.dumps(entry)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(entry)}\n\n"
        finally:
            orch.unsubscribe(server_id, queue)

    return StreamingResponse(gen(), media_type="text/event-stream")
