"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-13

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "server_state",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("cli_args", sa.JSON, nullable=False),
        sa.Column("telemetry_enabled", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("restart_policy", sa.String(16), nullable=False, server_default="on-failure"),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("server_state")
    op.drop_table("users")
