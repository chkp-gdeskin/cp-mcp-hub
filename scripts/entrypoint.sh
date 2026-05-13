#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "generate-key" ]]; then
  exec python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
fi

if [[ -z "${MASTER_KEY:-}" ]]; then
  echo "FATAL: MASTER_KEY env var is required. Generate one with: docker run --rm chkp-arose/cp-mcp-hub:latest generate-key" >&2
  exit 1
fi

if ! python3 -c "import sys; from cryptography.fernet import Fernet; Fernet(sys.argv[1])" "$MASTER_KEY" >/dev/null 2>&1; then
  echo "FATAL: MASTER_KEY is not a valid 32-byte url-safe base64 Fernet key. Regenerate with: docker run --rm chkp-arose/cp-mcp-hub:latest generate-key" >&2
  exit 1
fi

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR" "$DATA_DIR/logs" || {
  echo "FATAL: cannot write to $DATA_DIR. Mount it as a volume with appropriate ownership." >&2
  exit 1
}

# When running as root (e.g. first launch with a fresh volume), chown to the cpmcp user.
if [[ "$(id -u)" == "0" ]] && id -u cpmcp >/dev/null 2>&1; then
  chown -R cpmcp:cpmcp "$DATA_DIR" || true
  exec gosu cpmcp "$0" "$@"
fi

cd /app/backend
alembic upgrade head

exec uvicorn app.main:app --factory --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --no-access-log
