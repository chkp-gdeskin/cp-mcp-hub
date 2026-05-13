from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt
from app.core.security import generate_bearer_token, hash_password, utcnow
from app.db.models import ServerState, Setting, User
from app.manifest.loader import load_manifest

log = logging.getLogger("cpmcp.seed")

TOKEN_KEY = "sse_bearer_token"


async def seed_first_boot(db: AsyncSession) -> None:
    # admin user
    admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
    if admin is None:
        log.info("seeding admin user")
        db.add(User(
            username="admin",
            password_hash=hash_password("admin"),
            must_change_password=True,
            created_at=utcnow(),
        ))
    # bearer token
    token_row = await db.get(Setting, TOKEN_KEY)
    if token_row is None:
        log.info("seeding SSE bearer token")
        db.add(Setting(key=TOKEN_KEY, value=encrypt(generate_bearer_token()), updated_at=utcnow()))
    # one ServerState per manifest entry
    manifest = load_manifest()
    existing_ids = {r.id for r in (await db.execute(select(ServerState.id))).all()}
    # SQLAlchemy returns Row tuples here; rewrap
    existing = {r[0] if isinstance(r, tuple) else r for r in existing_ids}
    for s in manifest.servers:
        if s.id not in existing:
            db.add(ServerState(id=s.id, enabled=False, config={}, cli_args=[]))
    await db.commit()


async def ensure_data_dir(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
