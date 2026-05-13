#!/usr/bin/env sh
wget --no-verbose --tries=1 --spider "http://127.0.0.1:${PORT:-8000}/api/system/health" || exit 1
