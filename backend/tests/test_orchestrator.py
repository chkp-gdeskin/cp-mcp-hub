from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from app.orchestrator.process import SupervisedProcess
from app.orchestrator.ring_buffer import LogBuffer


async def test_ring_buffer_basic(tmp_path: Path):
    buf = LogBuffer("srv-test", tmp_path / "logs")
    for i in range(5):
        buf.append("stdout", f"line {i}")
    recent = buf.recent(3)
    assert [e["line"] for e in recent] == ["line 2", "line 3", "line 4"]
    log_file = tmp_path / "logs" / "srv-test.log"
    assert log_file.exists()


async def test_ring_buffer_pubsub(tmp_path: Path):
    buf = LogBuffer("srv-sub", tmp_path / "logs")
    q = buf.subscribe()
    buf.append("stderr", "hello")
    e = await asyncio.wait_for(q.get(), timeout=1.0)
    assert e["stream"] == "stderr"
    assert e["line"] == "hello"
    buf.unsubscribe(q)


@pytest.mark.skipif(shutil.which("python3") is None, reason="needs python3")
async def test_supervised_process_captures_lines():
    captured: list[tuple[str, str]] = []

    proc = SupervisedProcess(
        ["python3", "-c", "import sys; print('out-line'); print('err-line', file=sys.stderr)"],
        on_line=lambda stream, line: captured.append((stream, line.rstrip())),
    )
    await proc.start()
    rc = await proc.wait()
    assert rc == 0
    streams = {s for s, _ in captured}
    lines = {ln for _, ln in captured}
    assert "stdout" in streams and "stderr" in streams
    assert "out-line" in lines and "err-line" in lines


async def test_supervised_process_stop_terminates_quickly():
    proc = SupervisedProcess(["python3", "-c", "import time; time.sleep(30)"], on_line=lambda *_: None)
    await proc.start()
    rc = await asyncio.wait_for(proc.stop(timeout=3.0), timeout=5.0)
    assert rc is not None
    assert rc != 0  # SIGTERM-killed
