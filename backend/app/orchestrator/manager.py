from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
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
        # Servers the user has enabled (intended config).
        self._known_server_ids: set[str] = set()
        # Servers we believe are reachable through the proxy. Persists across
        # brief proxy restarts during reconciles so that toggling one server
        # doesn't flap the status of all the others. Cleared only on permanent
        # proxy failure or when a server is removed from _known_server_ids.
        self._running_servers: set[str] = set()
        # Hash of (config + bearer) that's currently applied to mcp-proxy.
        # Reconciles compare against this to skip redundant stop+start cycles.
        self._applied_config_hash: str | None = None
        # When True, the next proxy exit is expected (we requested it).
        # Prevents _await_exit from logging a failure and scheduling a
        # cascade of reconciles when we SIGTERM the proxy on purpose.
        self._intentional_stop: bool = False
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
        if server_id not in self._known_server_ids:
            return {"state": "disabled", "pid": None, "uptime_seconds": 0}
        if self._proxy_state == "failed":
            return {"state": "failed", "pid": None, "uptime_seconds": 0}
        # Optimistic running: if we believe this server is reachable, report
        # running even if the proxy is briefly between stop/start during a
        # reconcile triggered by toggling another server.
        if server_id in self._running_servers:
            if self._proxy_state == "running":
                uptime = int(time.time() - self._proxy_started_at) if self._proxy_started_at else 0
                pid = self._proc.pid if self._proc else None
                return {"state": "running", "pid": pid, "uptime_seconds": uptime}
            # Proxy is in transition (stopped/starting) but this server was
            # already running before the reconcile. Don't flap its UI.
            return {"state": "running", "pid": None, "uptime_seconds": 0}
        # Server is enabled but not yet known to be reachable (newly added).
        if self._proxy_state == "starting":
            return {"state": "starting", "pid": None, "uptime_seconds": 0}
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
            self._running_servers = set()
            self._applied_config_hash = None
            return

        # Compute a stable hash over the config and bearer. If nothing has
        # actually changed since the last successful start and the proxy is
        # still alive, this reconcile is a no-op. This prevents back-to-back
        # request_reconcile() calls (or stray events) from killing and
        # restarting mcp-proxy unnecessarily.
        config_blob = json.dumps(config, sort_keys=True) + "::" + (bearer or "")
        new_hash = hashlib.sha256(config_blob.encode()).hexdigest()
        if (
            new_hash == self._applied_config_hash
            and self._proc is not None
            and self._proc.running
            and self._proxy_state == "running"
        ):
            # Make sure the in-memory sets are consistent, but don't restart.
            self._known_server_ids = new_ids
            self._running_servers = set(new_ids)
            return

        write_proxy_config(self.config_path, config)

        await self._stop_proxy()
        # Drop any disabled servers from the optimistic running set, but keep
        # the rest so their UI doesn't flap to "starting" during this brief restart.
        self._running_servers &= new_ids
        self._known_server_ids = new_ids
        await self._start_proxy(bearer)
        if self._proxy_state == "running":
            self._applied_config_hash = new_hash

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
            self._running_servers = set()  # permanent failure invalidates optimistic state
            log.error("mcp-proxy: too many failures in 5min window, staying failed")
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
        # Reset the intentional-stop flag. Any subsequent exit of this fresh
        # proc that we haven't asked for is a real failure.
        self._intentional_stop = False
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
            self._running_servers = set(self._known_server_ids)
        else:
            log.warning("mcp-proxy did not become ready in time; continuing anyway")
            self._proxy_state = "running"
            self._proxy_started_at = time.time()
            self._running_servers = set(self._known_server_ids)

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
        # Mark this stop as intentional BEFORE sending SIGTERM. There's a race
        # between this function and _await_exit (both await proc.wait on the
        # same process). If _await_exit gets scheduled first when the proc
        # dies, it will check this flag, see True, and return without firing
        # a failure-driven reconcile.
        self._intentional_stop = True
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
        self._proxy_state = "stopped"
        self._proxy_started_at = None
        # If we asked for this stop (config reload, restart button, etc.),
        # don't treat it as a failure. Otherwise we'd record a failure for
        # every routine config change and oscillate via the backoff retry.
        if self._intentional_stop:
            log.info("mcp-proxy exited rc=%s (intentional)", rc)
            return
        log.warning("mcp-proxy exited unexpectedly rc=%s", rc)
        if rc != 0:
            self._failures.append(time.time())
            # Invalidate applied-config hash so the next reconcile actually
            # restarts (rather than thinking everything is still in place).
            self._applied_config_hash = None
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
