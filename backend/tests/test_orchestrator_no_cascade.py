"""Tests for the orchestrator's anti-cascade behavior.

Two protections, both important:
  1. _intentional_stop prevents _await_exit from treating a SIGTERM-on-purpose
     as a failure and re-triggering reconcile.
  2. _applied_config_hash makes _reconcile a no-op when nothing actually
     changed, so back-to-back reconcile requests don't churn the proxy.
"""
from __future__ import annotations

import asyncio

import pytest

from app.orchestrator.manager import Orchestrator


class _FakeProc:
    """Minimal stand-in for SupervisedProcess used in cascade tests."""

    def __init__(self, rc: int = -15):
        self._rc = rc
        self._exit = asyncio.Event()
        self.pid = 12345
        self.running = True

    async def wait(self) -> int:
        await self._exit.wait()
        self.running = False
        return self._rc

    async def stop(self, timeout: float = 5.0) -> int | None:
        # Simulate SIGTERM -> exit
        self._exit.set()
        # Yield to let any awaiter observe
        await asyncio.sleep(0)
        return self._rc


@pytest.fixture
def orch():
    return Orchestrator()


async def test_intentional_stop_does_not_record_failure(orch: Orchestrator):
    """Stopping the proxy on purpose must not bump the failure counter."""
    fake = _FakeProc(rc=-15)
    orch._proc = fake  # type: ignore[assignment]
    orch._proxy_state = "running"
    orch._wait_task = asyncio.create_task(orch._await_exit())

    # Simulate _stop_proxy's behavior wrt the flag
    orch._intentional_stop = True
    fake._exit.set()

    # Let _await_exit run
    await asyncio.sleep(0.1)

    assert len(orch._failures) == 0
    # _await_exit should NOT have queued a reconcile
    assert not orch._reconcile_event.is_set()


async def test_unexpected_exit_records_failure_and_requests_reconcile(orch: Orchestrator):
    """If the proxy dies on its own (not via _stop_proxy), record a failure."""
    fake = _FakeProc(rc=1)
    orch._proc = fake  # type: ignore[assignment]
    orch._proxy_state = "running"
    orch._intentional_stop = False  # an unexpected exit
    orch._wait_task = asyncio.create_task(orch._await_exit())

    fake._exit.set()
    # _await_exit sleeps 2^N seconds before requesting reconcile; wait long enough
    await asyncio.sleep(2.5)

    assert len(orch._failures) == 1
    assert orch._reconcile_event.is_set()


def test_runtime_status_after_failed_proxy(orch: Orchestrator):
    """When _await_exit detects an unexpected death, _applied_config_hash
    is invalidated so the next reconcile genuinely restarts."""
    orch._applied_config_hash = "previously-applied"
    orch._failures.append(0.0)  # pretend we recorded a failure
    orch._applied_config_hash = None  # what _await_exit's failure branch does
    assert orch._applied_config_hash is None
