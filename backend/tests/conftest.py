from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

# Set env BEFORE any `app.*` imports happen — this module is the first thing pytest loads.
_TMP = Path(tempfile.mkdtemp(prefix="cpmcp-test-"))
_DB = _TMP / "test.db"
os.environ.setdefault("MASTER_KEY", Fernet.generate_key().decode())
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB}"
os.environ["DATA_DIR"] = str(_TMP)

_repo_root = Path(__file__).resolve().parents[2]
_manifest_src = _repo_root / "server_definitions.json"
_manifest_dst = _TMP / "server_definitions.json"
if _manifest_src.exists():
    shutil.copy(_manifest_src, _manifest_dst)
os.environ["MANIFEST_PATH"] = str(_manifest_dst)
