from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from app.api import auth, logs, manifest, servers, system, token
from app.core.reverse_proxy import router as proxy_router
from app.db.session import get_session_factory
from app.orchestrator.manager import Orchestrator
from app.seed import ensure_data_dir, seed_first_boot
from app.settings import get_settings


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _setup_logging(settings.LOG_LEVEL)
    await ensure_data_dir(settings.DATA_DIR)
    factory = get_session_factory()
    async with factory() as db:
        await seed_first_boot(db)
    orchestrator = Orchestrator()
    await orchestrator.start()
    app.state.orchestrator = orchestrator
    app.state.external_base_url = os.environ.get("EXTERNAL_BASE_URL", "")
    try:
        yield
    finally:
        await orchestrator.stop()


def create_app() -> FastAPI:
    get_settings()  # validate env early
    app = FastAPI(title="cp-mcp-hub", version="0.1.0", lifespan=lifespan)

    # API routers
    app.include_router(auth.router)
    app.include_router(system.router)
    app.include_router(manifest.router)
    app.include_router(servers.router)
    app.include_router(logs.router)
    app.include_router(token.router)

    # Reverse proxy for SSE
    app.include_router(proxy_router)

    # SPA fallback
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
        index_path = static_dir / "index.html"

        @app.get("/", include_in_schema=False)
        async def root() -> FileResponse:
            return FileResponse(index_path)

        @app.exception_handler(404)
        async def spa_fallback(request: Request, exc: HTTPException) -> Response:
            # Only SPA-fallback for GETs that don't look like API calls
            path = request.url.path
            if request.method == "GET" and not path.startswith(("/api/", "/servers/", "/assets/")):
                return FileResponse(index_path)
            return JSONResponse({"error": "not_found", "message": exc.detail if isinstance(exc.detail, str) else "not found"}, status_code=404)

    return app


def app() -> FastAPI:  # for `uvicorn app.main:app --factory`
    return create_app()
