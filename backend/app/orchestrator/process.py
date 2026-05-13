from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Callable
from typing import Any


class SupervisedProcess:
    """Async subprocess wrapper that streams stdout/stderr to a callback."""

    def __init__(
        self,
        argv: list[str],
        env: dict[str, str] | None = None,
        on_line: Callable[[str, str], None] | None = None,
    ):
        self.argv = argv
        self.env = env
        self.on_line = on_line
        self._proc: asyncio.subprocess.Process | None = None
        self._readers: list[asyncio.Task[Any]] = []

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode if self._proc else None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> None:
        env = {**os.environ, **(self.env or {})}
        self._proc = await asyncio.create_subprocess_exec(
            *self.argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        assert self._proc.stdout and self._proc.stderr
        self._readers = [
            asyncio.create_task(self._read("stdout", self._proc.stdout)),
            asyncio.create_task(self._read("stderr", self._proc.stderr)),
        ]

    async def _read(self, stream: str, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                try:
                    text = raw.decode("utf-8", errors="replace")
                except Exception:
                    continue
                if self.on_line:
                    self.on_line(stream, text)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def wait(self) -> int:
        assert self._proc is not None
        rc = await self._proc.wait()
        for t in self._readers:
            try:
                await asyncio.wait_for(t, timeout=2.0)
            except (TimeoutError, asyncio.CancelledError):
                t.cancel()
        return rc

    async def stop(self, timeout: float = 5.0) -> int | None:
        if not self._proc or self._proc.returncode is not None:
            return self._proc.returncode if self._proc else None
        try:
            self._proc.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            return self._proc.returncode
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=timeout)
        except TimeoutError:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except TimeoutError:
                pass
        for t in self._readers:
            t.cancel()
        return self._proc.returncode
