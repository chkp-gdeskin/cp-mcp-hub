from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.models import Base
from app.db.session import get_engine, get_session_factory
from app.main import create_app
from app.seed import seed_first_boot


@pytest.fixture
async def app_client():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory()
    async with factory() as db:
        await seed_first_boot(db)
    app = create_app()
    # Skip lifespan (orchestrator)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))
        await conn.execute(text("DELETE FROM server_state"))
        await conn.execute(text("DELETE FROM settings"))


async def test_login_required_then_succeeds(app_client: AsyncClient):
    r = await app_client.get("/api/servers")
    assert r.status_code == 401

    r = await app_client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["must_change_password"] is True

    r = await app_client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["must_change_password"] is True


async def test_change_password_clears_flag(app_client: AsyncClient):
    await app_client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    r = await app_client.post(
        "/api/auth/change-password",
        json={"old_password": "admin", "new_password": "new-very-strong-pw!"},
    )
    assert r.status_code == 200
    r = await app_client.get("/api/auth/me")
    assert r.json()["must_change_password"] is False


async def test_change_password_min_length(app_client: AsyncClient):
    await app_client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    r = await app_client.post(
        "/api/auth/change-password",
        json={"old_password": "admin", "new_password": "short"},
    )
    assert r.status_code == 422
