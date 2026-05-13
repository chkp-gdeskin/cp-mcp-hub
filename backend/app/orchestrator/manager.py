from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections import deque
from typing import Any

import httpx

from app.core.encryption import decrypt
from app.db.models import Setting
from app.db.session import get_session_factory
from app.orchestrator.process import SupervisedProcess
from app.orchestrator.proxy_config import build_named_servers_config, write_proxy_config
from app.orchestrator.ring_buffer import LogBuffer
from app.settings import get_settings

log = logging.getLogger("cpmcp.orchestrator")

PROXY_LINE_PREFIX = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?\[?(?P<name>[a-z0-9][a-z0-9-]+)\]?\s*[:|]\s*(?P<rest>.*)$", re.I)


class Orchestrator:
    """Owns the single mcp-proxy child process and per-server log buffers."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.config_path = self.settings.DATA_DIR / "mcp-proxy-config.json"
        self.logs_dir = self.settings.DATA_DIR / "logs"
        self._proc: SupervisedProcess | None = None
        self._wait_task: asyncio.Task[Any] | None = None
        self._reconcile_event = asyncio.Event()
        self._reconcile_task: asyncio.Task[Any] | None = None
        self._buffers: dict[str, LogBuffer] = {}
        self._proxy_state: str = "stopped"
        self._proxy_started_at: float | None = None
        self._failures: deque[float] = deque(maxlen=5)
        self._known_server_ids: set[str] = set()
        self._http: httpx.AsyncClient | None = None

    # ---- lifecycle ----

    async def start(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._http = httpx.AsyncClient(timeout=5.0)
        self._reconcile_task = asyncio.create_task(self._reconcile_loop(), name="orch.reconcile")
        await self.request_reconcile()

    async def stop(self) -> None:
        if self._reconcile_task:
            self._reconcile_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconcile_task
        await self._stop_proxy()
        if self._http:
            await self._http.aclose()
            self._http = None

    # ---- state queries ----

    def proxy_state(self) -> str:
        return self._proxy_state

    def _buffer(self, server_id: str) -> LogBuffer:
        buf = self._buffers.get(server_id)
        if buf is None:
            buf = LogBuffer(server_id, self.logs_dir)
            self._buffers[server_id] = buf
        return buf

    def recent_logs(self, server_id: str, n: int) -> list[dict[str, Any]]:
        return self._buffer(server_id).recent(n)

    def subscribe(self, server_id: str) -> asyncio.Queue:
        return self._buffer(server_id).subscribe()

    def unsubscribe(self, server_id: str, queue: asyncio.Queue) -> None:
        self._buffer(server_id).unsubscribe(queue)

    def runtime_status(self, server_id: str) -> dict[str, Any]:
        in_enabled_set = server_id in self._known_server_ids
        if not in_enabled_set:
            return {"state": "disabled", "pid": None, "uptime_seconds": 0}
        if self._proxy_state == "running":
            uptime = int(time.time() - self._proxy_started_at) if self._proxy_started_at else 0
            return {"state": "running", "pid": self._proc.pid if self._proc else None, "uptime_seconds": uptime}
        if self._proxy_state == "starting":
            return {"state": "starting", "pid": None, "uptime_seconds": 0}
        if self._proxy_state == "failed":
            return {"state": "failed", "pid": None, "uptime_seconds": 0}
        return {"state": "stopped", "pid": None, "uptime_seconds": 0}

    # ---- reconciliation ----

    async def request_reconcile(self) -> None:
        self._reconcile_event.set()

    async def restart_proxy(self) -> None:
        await self._stop_proxy()
        await self.request_reconcile()

    async def _reconcile_loop(self) -> None:
        try:
            while True:
                await self._reconcile_event.wait()
                self._reconcile_event.clear()
                try:
                    await self._reconcile()
                except Exception:
                    log.exception("reconcile failed")
                # Debounce — coalesce rapid-fire events
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            return

    async def _reconcile(self) -> None:
        factory = get_session_factory()
        async with factory() as db:
            config = await build_named_servers_config(db)
            bearer = await self._read_bearer(db)
        new_ids = set(config["mcpServers"].keys())

        if not new_ids:
            await self._stop_proxy()
            self._known_server_ids = set()
            return

        write_proxy_config(self.config_path, config)

        # If proxy is already running with the same set of servers, just restart to pick up config changes.
        await self._stop_proxy()
        self._known_server_ids = new_ids
        await self._start_proxy(bearer)

    async def _read_bearer(self, db) -> str:
        from app.api.token import TOKEN_KEY
        row = await db.get(Setting, TOKEN_KEY)
        if row is None:
            return ""
        try:
            return decrypt(row.value)
        except Exception:
            return ""

    # ---- proxy process ----

    async def _start_proxy(self, bearer: str) -> None:
        if self._proc and self._proc.running:
            return
        # Backoff if we are failing repeatedly
        now = time.time()
        recent = [t for t in self._failures if now - t < 300]
        if len(recent) >= 5:
            self._proxy_state = "failed"
            log.error("mcp-proxy: too many failures in 5min window — staying failed")
            return

        argv = [
            "mcp-proxy",
            "--named-server-config", str(self.config_path),
            "--host", "127.0.0.1",
            "--port", str(self.settings.MCP_PROXY_PORT),
            "--allow-origin", "*",
        ]
        env = {}
        if bearer:
            env["API_ACCESS_TOKEN"] = bearer

        self._proxy_state = "starting"
        self._proxy_started_at = None
        proc = SupervisedProcess(argv, env=env, on_line=self._on_proxy_line)
        try:
            await proc.start()
        except FileNotFoundError:
            log.error("mcp-proxy not found on PATH")
            self._failures.append(now)
            self._proxy_state = "failed"
            return
        self._proc = proc
        self._wait_task = asyncio.create_task(self._await_exit(), name="orch.proxy_wait")
        # Wait until /status responds 200, or timeout
        if await self._wait_for_ready(timeout=15.0):
            self._proxy_state = "running"
            self._proxy_started_at = time.time()
        else:
            log.warning("mcp-proxy did not become ready in time; continuing anyway")
            self._proxy_state = "running"
            self._proxy_started_at = time.time()

    async def _wait_for_ready(self, timeout: float) -> bool:
        if not self._http:
            return False
        deadline = time.time() + timeout
        url = f"http://127.0.0.1:{self.settings.MCP_PROXY_PORT}/status"
        while time.time() < deadline:
            try:
                r = await self._http.get(url, timeout=2.0)
                if r.status_code < 500:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def _stop_proxy(self) -> None:
        if self._proc is None:
            return
        try:
            await self._proc.stop(timeout=5.0)
        except Exception:
            log.exception("error stopping mcp-proxy")
        if self._wait_task:
            self._wait_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._wait_task
            self._wait_task = None
        self._proc = None
        self._proxy_state = "stopped"
        self._proxy_started_at = None

    async def _await_exit(self) -> None:
        assert self._proc is not None
        rc = await self._proc.wait()
        log.warning("mcp-proxy exited rc=%s", rc)
        self._proxy_state = "stopped"
        self._proxy_started_at = None
        if rc != 0:
            self._failures.append(time.time())
            # Auto-restart by triggering reconcile
            await asyncio.sleep(min(2 ** len(self._failures), 16))
            await self.request_reconcile()

    # ---- log fan-out ----

    def _on_proxy_line(self, stream: str, raw: str) -> None:
        # mcp-proxy combined log: try to extract a server-name prefix; otherwise drop to a global bucket.
        server_id: str | None = None
        rest = raw
        m = PROXY_LINE_PREFIX.match(raw)
        if m:
            name = m.group("name")
            if name in self._known_server_ids:
                server_id = name
                rest = m.group("rest")
        if server_id:
            self._buffer(server_id).append(stream, rest)
        else:
            # Distribute to all known servers as a global system line
            for sid in self._known_server_ids:
                self._buffer(sid).append("system", raw)
