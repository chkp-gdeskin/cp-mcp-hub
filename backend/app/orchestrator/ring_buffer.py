from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

MAX_LINES = 1000
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 3


class LogBuffer:
    """Per-server in-memory ring buffer + file appender + async subscribers."""

    def __init__(self, server_id: str, logs_dir: Path):
        self.server_id = server_id
        self._lines: deque[dict[str, Any]] = deque(maxlen=MAX_LINES)
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        logs_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(f"cpmcp.server.{server_id}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        # Avoid duplicate handlers if buffer is recreated
        if not self._logger.handlers:
            handler = RotatingFileHandler(
                logs_dir / f"{server_id}.log",
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            self._logger.addHandler(handler)

    def append(self, stream: str, line: str) -> None:
        line = line.rstrip("\n")
        entry = {"ts": time.time(), "stream": stream, "line": line}
        self._lines.append(entry)
        self._logger.info("[%s] %s", stream, line)
        dead: list[asyncio.Queue[dict[str, Any]]] = []
        for q in self._subscribers:
            try:
                q.put_nowait(entry)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def recent(self, count: int) -> list[dict[str, Any]]:
        if count >= len(self._lines):
            return list(self._lines)
        return list(self._lines)[-count:]

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass
