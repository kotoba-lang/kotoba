"""Live-fleet smoke tests.

Skipped unless ``KOTOBA_MURAKUMO_LIVE_FLEET=1``. Run from a host on the
Murakumo LAN (192.168.1.0/24) with judah :4000 + evo-x2 :11434 reachable.

Mark each test with ``@pytest.mark.live_fleet``; ``conftest.py`` auto-skips
unless the env var is set.
"""

from __future__ import annotations

import socket

import pytest

from kotoba_murakumo import App, gpu

pytestmark = pytest.mark.live_fleet


def _lan_reachable(host: str, port: int, *, timeout_s: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def test_live_litellm_gateway_round_trip(fleet_path) -> None:
    if not _lan_reachable("192.168.1.17", 4000):
        pytest.skip("judah :4000 not reachable from this host")
    app = App("live-smoke", fleet=fleet_path, did="did:web:smoke.etzhayyim.com")

    @app.function(model="gemma3:4b")  # routed to judah :4000
    def echo(prompt: str) -> str: ...

    out = echo.remote("Reply with the single word: alive")
    assert isinstance(out, str) and len(out) > 0


def test_live_evo_x2_ollama_round_trip(fleet_path) -> None:
    if not _lan_reachable("192.168.1.70", 11434):
        pytest.skip("evo-x2 :11434 not reachable from this host")
    app = App("live-smoke", fleet=fleet_path)

    @app.function(gpu=gpu.EvoX2(prefer="ollama"), model="llama3.2:3b")
    def reply(prompt: str) -> str: ...

    out = reply.remote("Reply with one short word.")
    assert isinstance(out, str) and len(out) > 0
