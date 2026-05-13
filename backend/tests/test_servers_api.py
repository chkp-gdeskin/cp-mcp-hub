from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.servers import SECRET_PLACEHOLDER
from app.db.models import Base, ServerState
from app.db.session import get_engine, get_session_factory
from app.main import create_app
from app.manifest.loader import load_manifest
from app.seed import seed_first_boot


@pytest.fixture
async def client_with_session():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory()
    async with factory() as db:
        await seed_first_boot(db)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        yield client
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))
        await conn.execute(text("DELETE FROM server_state"))
        await conn.execute(text("DELETE FROM settings"))


async def test_list_servers_matches_manifest(client_with_session: AsyncClient):
    r = await client_with_session.get("/api/servers")
    assert r.status_code == 200
    items = r.json()["servers"]
    assert len(items) == len(load_manifest().servers)
    assert all(item["enabled"] is False for item in items)


async def test_secret_field_roundtrip(client_with_session: AsyncClient):
    m = load_manifest()
    target = next((s for s in m.servers if any(ev.secret for ev in s.env_vars)), None)
    assert target is not None
    secret_name = next(ev.name for ev in target.env_vars if ev.secret)

    # Save with a secret value
    r = await client_with_session.put(
        f"/api/servers/{target.id}/config",
        json={"config": {secret_name: "super-secret-value"}, "cli_args": [], "telemetry_enabled": False, "restart_policy": "on-failure"},
    )
    assert r.status_code == 200

    # GET must return placeholder, never plaintext
    r = await client_with_session.get(f"/api/servers/{target.id}")
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert cfg[secret_name] == SECRET_PLACEHOLDER

    # Re-save with placeholder must preserve value
    r = await client_with_session.put(
        f"/api/servers/{target.id}/config",
        json={"config": {secret_name: SECRET_PLACEHOLDER}, "cli_args": [], "telemetry_enabled": False, "restart_policy": "on-failure"},
    )
    assert r.status_code == 200

    factory = get_session_factory()
    async with factory() as db:
        row = (await db.execute(select(ServerState).where(ServerState.id == target.id))).scalar_one()
        # Stored value should still be valid Fernet ciphertext that decrypts to the original
        from app.core.encryption import decrypt
        assert decrypt(row.config[secret_name]) == "super-secret-value"


async def test_enable_requires_required_fields(client_with_session: AsyncClient):
    m = load_manifest()
    target = next((s for s in m.servers if any(ev.required for ev in s.env_vars)), None)
    if target is None:
        pytest.skip("no server has required fields")
    r = await client_with_session.post(f"/api/servers/{target.id}/enable")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["missing_required"]
