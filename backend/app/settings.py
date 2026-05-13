from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    MASTER_KEY: str
    SECRET_KEY: str | None = None
    DATABASE_URL: str = "sqlite+aiosqlite:////data/cp-mcp-hub.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    MCP_PROXY_PORT: int = 8001
    LOG_LEVEL: str = "INFO"
    DATA_DIR: Path = Path("/data")
    MANIFEST_PATH: Path = Path("/app/server_definitions.json")

    @field_validator("MASTER_KEY")
    @classmethod
    def _validate_master_key(cls, v: str) -> str:
        try:
            Fernet(v.encode() if isinstance(v, str) else v)
        except (InvalidToken, ValueError, TypeError) as exc:
            raise ValueError(
                f"MASTER_KEY is not a valid 32-byte url-safe base64 Fernet key: {exc}. "
                "Generate one with: docker run --rm aaronroseio/cp-mcp-hub generate-key"
            ) from exc
        return v


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        print(f"FATAL: settings error: {exc}", file=sys.stderr)
        raise
