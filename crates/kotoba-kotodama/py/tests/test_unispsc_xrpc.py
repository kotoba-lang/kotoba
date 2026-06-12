"""Unit tests for the /xrpc/com.etzhayyim.apps.unispsc.* façade.

Each test pokes a single endpoint through FastAPI's TestClient. The
``invokeAgent`` test exercises the just-fixed SDRAM (c32101621) module and
the DRAM (c32101602) module to confirm the lazy-load + ainvoke path works
without contacting the actual upstream langserver pod.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kotodama.xrpc.unispsc import router as unispsc_router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(unispsc_router)
    return TestClient(app)


def test_health_reports_registry_ready(client: TestClient) -> None:
    r = client.get("/xrpc/com.etzhayyim.apps.unispsc.health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["registryReady"] is True
    assert body["agentCount"] >= 18_000
    assert "haiku-4.5" in body["modelsAvailable"]


def test_list_agents_pagination_and_prefix(client: TestClient) -> None:
    r = client.get("/xrpc/com.etzhayyim.apps.unispsc.listAgents", params={"prefix": "321016", "limit": 50})
    assert r.status_code == 200
    body = r.json()
    codes = [a["code"] for a in body["agents"]]
    assert "32101602" in codes  # DRAM
    assert "32101621" in codes  # SDRAM
    assert all(c.startswith("321016") for c in codes)
    assert all(a["module"].endswith(f".c{a['code']}") for a in body["agents"])


def test_invoke_dram_agent_passes_validation(client: TestClient) -> None:
    r = client.post(
        "/xrpc/com.etzhayyim.apps.unispsc.invokeAgent",
        json={
            "code": "32101602",
            "payload": {
                "spec_data": {"clock_speed_mhz": 3200},
                "validation_errors": [],
                "is_compliant": False,
            },
            "timeoutMs": 5000,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["is_compliant"] is True
    assert body["result"]["validation_errors"] == []


def test_invoke_dram_agent_flags_low_clock_speed(client: TestClient) -> None:
    r = client.post(
        "/xrpc/com.etzhayyim.apps.unispsc.invokeAgent",
        json={
            "code": "32101602",
            "payload": {
                "spec_data": {"clock_speed_mhz": 1066},
                "validation_errors": [],
                "is_compliant": False,
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["is_compliant"] is False
    assert "Insufficient clock speed" in body["result"]["validation_errors"]


def test_invoke_sdram_agent_after_syntax_fix(client: TestClient) -> None:
    """c32101621.py was previously SyntaxError; this confirms the fix loads."""
    r = client.post(
        "/xrpc/com.etzhayyim.apps.unispsc.invokeAgent",
        json={
            "code": "32101621",
            "payload": {
                "specs": {"frequency": 3200},
                "validation_errors": [],
                "approved": False,
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["approved"] is True


def test_invoke_unknown_code_returns_404(client: TestClient) -> None:
    r = client.post(
        "/xrpc/com.etzhayyim.apps.unispsc.invokeAgent",
        json={"code": "99999999", "payload": {}},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "AgentNotFound"
