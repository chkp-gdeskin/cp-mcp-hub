# syntax=docker/dockerfile:1.7

# Stage 1 — frontend build
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2 — runtime: Python 3.12 base + Node 22 from NodeSource
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    MCP_PROXY_PORT=8001 \
    DATA_DIR=/data \
    MANIFEST_PATH=/app/server_definitions.json

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg tini gosu wget \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get purge -y curl gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /bin/false --uid 10001 cpmcp

# Python deps
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir \
      'fastapi>=0.115' \
      'uvicorn[standard]>=0.32' \
      'sqlalchemy>=2.0' \
      'alembic>=1.13' \
      'aiosqlite>=0.20' \
      'greenlet>=3' \
      'pydantic>=2.8' \
      'pydantic-settings>=2.5' \
      'cryptography>=43' \
      'bcrypt>=4.2' \
      'httpx>=0.27' \
      'anyio>=4' \
      'itsdangerous>=2.2' \
      'mcp-proxy==0.11.0'

# Install CP MCP server packages globally so npx can launch them without network at runtime.
# Use || true on each to tolerate any package that isn't published under the expected name yet.
RUN --mount=type=cache,target=/root/.npm \
    set -eux; \
    for pkg in \
      @chkp/quantum-management-mcp \
      @chkp/management-logs-mcp \
      @chkp/threat-prevention-mcp \
      @chkp/https-inspection-mcp \
      @chkp/harmony-sase-mcp \
      @chkp/reputation-service-mcp \
      @chkp/quantum-gw-cli-mcp \
      @chkp/quantum-gw-connection-analysis-mcp \
      @chkp/threat-emulation-mcp \
      @chkp/quantum-gaia-mcp \
      @chkp/documentation-mcp \
      @chkp/spark-management-mcp \
      @chkp/cpinfo-analysis-mcp \
      @chkp/argos-erm-mcp \
      @chkp/policy-insights-mcp ; do \
        npm install -g --omit=optional "$pkg" || echo "WARN: $pkg not installable, skipping"; \
    done

COPY backend/app /app/backend/app
COPY backend/alembic.ini /app/backend/alembic.ini
COPY --from=frontend /app/frontend/dist /app/backend/static
COPY server_definitions.json /app/server_definitions.json
COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/healthcheck.sh /healthcheck.sh
COPY scripts/gen_tls.py /app/scripts/gen_tls.py
RUN chmod +x /entrypoint.sh /healthcheck.sh \
 && mkdir -p /data \
 && chown -R cpmcp:cpmcp /data /app

WORKDIR /app/backend
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD /healthcheck.sh

ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
