from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.manifest.schema import Manifest, ServerDefinition
from app.settings import get_settings


@lru_cache
def load_manifest() -> Manifest:
    path: Path = get_settings().MANIFEST_PATH
    if not path.exists():
        # Fall back to repo-root location during dev
        alt = Path(__file__).resolve().parents[3] / "server_definitions.json"
        if alt.exists():
            path = alt
    data = json.loads(path.read_text())
    return Manifest.model_validate(data)


def get_server_def(server_id: str) -> ServerDefinition | None:
    for s in load_manifest().servers:
        if s.id == server_id:
            return s
    return None
