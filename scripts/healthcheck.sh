#!/usr/bin/env sh
# Runs INSIDE the container. $PORT is the container-internal listening port
# (set to 8000 by the Dockerfile). Host-side port mappings via `-p HOST:8090`
# don't affect this — we always hit 127.0.0.1:$PORT inside the container.
#
# We do a real GET (not --spider, which sends HEAD and trips on routes that
# only accept GET) and discard the body. Non-2xx makes wget exit non-zero,
# which Docker reports as unhealthy.
wget --no-verbose --tries=1 --timeout=5 -O /dev/null "http://127.0.0.1:${PORT:-8000}/api/system/health" || exit 1
