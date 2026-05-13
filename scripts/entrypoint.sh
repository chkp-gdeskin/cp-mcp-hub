#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "generate-key" ]]; then
  exec python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
fi

if [[ -z "${MASTER_KEY:-}" ]]; then
  echo "FATAL: MASTER_KEY env var is required. Generate one with: docker run --rm aaronroseio/cp-mcp-hub:latest generate-key" >&2
  exit 1
fi

if ! python3 -c "import sys; from cryptography.fernet import Fernet; Fernet(sys.argv[1])" "$MASTER_KEY" >/dev/null 2>&1; then
  echo "FATAL: MASTER_KEY is not a valid 32-byte url-safe base64 Fernet key. Regenerate with: docker run --rm aaronroseio/cp-mcp-hub:latest generate-key" >&2
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

# Optional TLS: ENABLE_TLS=true serves uvicorn over HTTPS with a self-signed
# cert (generated on first boot, persisted in /data/tls). Required for Claude
# Desktop / Claude Code's "remote URL" integration, which rejects plain HTTP.
TLS_ARGS=()
if [[ "${ENABLE_TLS:-false}" == "true" ]]; then
  TLS_CERT_PATH="${TLS_CERT_PATH:-$DATA_DIR/tls/cert.pem}"
  TLS_KEY_PATH="${TLS_KEY_PATH:-$DATA_DIR/tls/key.pem}"
  TLS_HOSTNAMES="${TLS_HOSTNAMES:-localhost,127.0.0.1}"
  python3 /app/scripts/gen_tls.py "$TLS_CERT_PATH" "$TLS_KEY_PATH" "$TLS_HOSTNAMES"
  TLS_ARGS+=(--ssl-keyfile "$TLS_KEY_PATH" --ssl-certfile "$TLS_CERT_PATH")
fi

exec uvicorn app.main:app --factory --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --no-access-log "${TLS_ARGS[@]}"
