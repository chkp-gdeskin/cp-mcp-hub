#!/usr/bin/env sh
# Runs INSIDE the container. $PORT is the container-internal listening port
# (set to 8000 by the Dockerfile). Host-side port mappings via `-p HOST:8000`
# don't affect this — we always hit 127.0.0.1:$PORT inside the container.
wget --no-verbose --tries=1 --spider "http://127.0.0.1:${PORT:-8000}/api/system/health" || exit 1
