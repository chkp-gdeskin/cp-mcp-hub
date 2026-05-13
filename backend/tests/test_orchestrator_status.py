"""Unit tests for Orchestrator.runtime_status — the optimistic-running logic
that prevents one server's toggle from flapping all the others' UI."""
from __future__ import annotations

from app.orchestrator.manager import Orchestrator


def _orch() -> Orchestrator:
    # Note: Orchestrator.__init__ reads settings, which is fine in test env (conftest sets envs)
    return Orchestrator()


def test_disabled_when_not_in_known():
    o = _orch()
    o._known_server_ids = {"a"}
    assert o.runtime_status("b")["state"] == "disabled"


def test_running_when_in_running_servers_and_proxy_running():
    o = _orch()
    o._known_server_ids = {"a"}
    o._running_servers = {"a"}
    o._proxy_state = "running"
    o._proxy_started_at = 0.0
    assert o.runtime_status("a")["state"] == "running"


def test_optimistic_running_during_proxy_restart():
    """Server A was running. User enables B. Proxy briefly stops/starts.
    A should NOT flap to 'starting' or 'stopped' just because the proxy is
    in transition."""
    o = _orch()
    o._known_server_ids = {"a", "b"}
    o._running_servers = {"a"}  # b not yet running

    # proxy_state == "stopped" mid-reconcile
    o._proxy_state = "stopped"
    assert o.runtime_status("a")["state"] == "running"   # optimistic
    assert o.runtime_status("b")["state"] == "stopped"

    # proxy_state == "starting"
    o._proxy_state = "starting"
    assert o.runtime_status("a")["state"] == "running"   # still optimistic
    assert o.runtime_status("b")["state"] == "starting"  # newly added, honestly starting


def test_failed_proxy_overrides_optimistic_running():
    o = _orch()
    o._known_server_ids = {"a"}
    o._running_servers = {"a"}
    o._proxy_state = "failed"
    assert o.runtime_status("a")["state"] == "failed"


def test_newly_added_server_shows_starting():
    o = _orch()
    o._known_server_ids = {"a"}
    o._running_servers = set()
    o._proxy_state = "starting"
    assert o.runtime_status("a")["state"] == "starting"


def test_known_but_not_running_with_proxy_stopped_shows_stopped():
    o = _orch()
    o._known_server_ids = {"a"}
    o._running_servers = set()
    o._proxy_state = "stopped"
    assert o.runtime_status("a")["state"] == "stopped"
