"""Pure tests for langgraph_server_app.py (ADR-2605080600 Phase 2).

No RisingWave, no LLM, no Zeebe required.

Coverage:
- GET  /healthz              — always 200
- GET  /assistants           — reflects _GRAPH_REGISTRY
- POST /threads              — returns thread_id
- POST /runs 404             — unknown assistant_id
- POST /runs 202             — known assistant_id, background tasks patched
- GET  /runs/{id}            — status pending then success
- GET  /runs/{id} 404        — unknown run_id
- GET  /readyz 503           — DB unreachable
- Module-level state isolation between tests
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_state():
    """Clear module-level _RUNS and _GRAPH_REGISTRY before/after each test."""
    from kotodama import langgraph_server_app as mod
    mod._RUNS.clear()
    mod._GRAPH_REGISTRY.clear()
    yield
    mod._RUNS.clear()
    mod._GRAPH_REGISTRY.clear()


@pytest.fixture()
def client():
    """TestClient — lifespan runs (registers builtins), then we clear so tests start clean."""
    from kotodama.langgraph_server_app import app
    from kotodama import langgraph_server_app as mod
    with TestClient(app, raise_server_exceptions=True) as c:
        # lifespan has fired and may have populated _GRAPH_REGISTRY; reset for test isolation.
        mod._RUNS.clear()
        mod._GRAPH_REGISTRY.clear()
        yield c


@pytest.fixture()
def client_with_echo(client):
    """Register a minimal echo graph before yielding the client."""
    from kotodama.langgraph_server_app import register_graph
    from langgraph.graph import END, StateGraph
    from typing import TypedDict

    class _Echo(TypedDict):
        input: str
        output: str

    builder = StateGraph(_Echo)
    builder.add_node("echo", lambda s: {"output": f"echo:{s.get('input','')}"})
    builder.set_entry_point("echo")
    builder.add_edge("echo", END)
    register_graph("echo", builder.compile())
    yield client


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------

def test_healthz_returns_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["service"] == "langgraph-server"


# ---------------------------------------------------------------------------
# /assistants
# ---------------------------------------------------------------------------

def test_assistants_empty_registry(client):
    resp = client.get("/assistants")
    assert resp.status_code == 200
    assert resp.json() == []


def test_assistants_lists_registered(client_with_echo):
    resp = client_with_echo.get("/assistants")
    assert resp.status_code == 200
    aids = [a["assistant_id"] for a in resp.json()]
    assert "echo" in aids


# ---------------------------------------------------------------------------
# POST /threads
# ---------------------------------------------------------------------------

def test_create_thread_returns_thread_id(client):
    resp = client.post("/threads", json={"assistant_id": "echo"})
    assert resp.status_code == 201
    body = resp.json()
    assert "thread_id" in body
    assert body["assistant_id"] == "echo"
    assert isinstance(body["created_at"], int)


# ---------------------------------------------------------------------------
# POST /runs
# ---------------------------------------------------------------------------

def test_create_run_unknown_assistant_404(client):
    resp = client.post("/runs", json={"assistant_id": "nonexistent"})
    assert resp.status_code == 404
    assert "nonexistent" in resp.json()["detail"]


@patch("kotodama.langgraph_server_app._rw_upsert_run", new_callable=AsyncMock)
@patch("kotodama.langgraph_server_app._execute_graph", new_callable=AsyncMock)
def test_create_run_returns_202(mock_exec, mock_upsert, client_with_echo):
    resp = client_with_echo.post(
        "/runs",
        json={"assistant_id": "echo", "input": {"input": "hello"}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert "run_id" in body
    assert "thread_id" in body


@patch("kotodama.langgraph_server_app._rw_upsert_run", new_callable=AsyncMock)
@patch("kotodama.langgraph_server_app._execute_graph", new_callable=AsyncMock)
def test_create_run_uses_provided_thread_id(mock_exec, mock_upsert, client_with_echo):
    resp = client_with_echo.post(
        "/runs",
        json={"assistant_id": "echo", "thread_id": "tid-abc123", "input": {}},
    )
    assert resp.status_code == 202
    assert resp.json()["thread_id"] == "tid-abc123"


# ---------------------------------------------------------------------------
# GET /runs/{run_id}
# ---------------------------------------------------------------------------

@patch("kotodama.langgraph_server_app._rw_upsert_run", new_callable=AsyncMock)
@patch("kotodama.langgraph_server_app._execute_graph", new_callable=AsyncMock)
def test_get_run_pending(mock_exec, mock_upsert, client_with_echo):
    create_resp = client_with_echo.post(
        "/runs",
        json={"assistant_id": "echo", "input": {"input": "hi"}},
    )
    run_id = create_resp.json()["run_id"]

    get_resp = client_with_echo.get(f"/runs/{run_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["run_id"] == run_id
    assert body["status"] == "pending"
    assert body["output"] is None


def test_get_run_unknown_404(client):
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


@patch("kotodama.langgraph_server_app._rw_upsert_run", new_callable=AsyncMock)
@patch("kotodama.langgraph_server_app._execute_graph", new_callable=AsyncMock)
def test_get_run_success_state(mock_exec, mock_upsert, client_with_echo):
    """Manually set run to success and verify GET reflects it."""
    from kotodama import langgraph_server_app as mod

    create_resp = client_with_echo.post(
        "/runs",
        json={"assistant_id": "echo", "input": {"input": "world"}},
    )
    run_id = create_resp.json()["run_id"]

    # simulate completed run
    mod._RUNS[run_id]["status"] = "success"
    mod._RUNS[run_id]["output_json"] = json.dumps({"output": "echo:world"})
    mod._RUNS[run_id]["completed_at"] = 1_000_000

    get_resp = client_with_echo.get(f"/runs/{run_id}")
    body = get_resp.json()
    assert body["status"] == "success"
    assert body["output"] == {"output": "echo:world"}
    assert body["completed_at"] == 1_000_000


# ---------------------------------------------------------------------------
# GET /readyz — DB unreachable returns 503
# ---------------------------------------------------------------------------

def test_readyz_db_unreachable_503(client):
    with patch(
        "kotodama.langgraph_server_app.ensure_rw_async_pool",
        new_callable=AsyncMock,
        side_effect=RuntimeError("RW_URL not set"),
    ):
        resp = client.get("/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ok"] is False
    assert body["db"] == "unreachable"
