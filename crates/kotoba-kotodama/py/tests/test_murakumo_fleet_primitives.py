"""Tests for murakumo_fleet primitives."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import pytest
from kotodama.primitives import murakumo_fleet as MF  # noqa: E402


@pytest.fixture()
def _stub_db():
    with patch("kotodama.primitives.murakumo_fleet.sync_cursor") as m:
        cur = MagicMock()
        m.return_value.__enter__ = MagicMock(return_value=cur)
        m.return_value.__exit__ = MagicMock(return_value=False)
        yield cur


# ─── _extract_node_name (pure) ───────────────────────────────────────────────

def test_extract_node_name_known_ip():
    assert MF._extract_node_name("http://192.168.1.61:11434") == "judah"


def test_extract_node_name_another_known_ip():
    assert MF._extract_node_name("http://192.168.1.51:11434") == "benjamin"


def test_extract_node_name_unknown_ip():
    assert MF._extract_node_name("http://10.0.0.1:11434") == "unknown"


def test_extract_node_name_empty():
    assert MF._extract_node_name("") == "unknown"


# ─── build_fleet_roster (pure) ───────────────────────────────────────────────

def test_build_fleet_roster_unreachable_probe():
    probe = {"reachable": False, "error": "transport error", "latencyMs": 100}
    roster = MF.build_fleet_roster(probe)
    assert roster["healthPct"] == 0
    assert roster["nodesHealthy"] == 0
    assert roster["nodesTotal"] == len(MF.FLEET_NODES)
    assert roster["litellm"]["reachable"] is False
    assert "ts" in roster


def test_build_fleet_roster_reachable_with_deployments():
    probe = {
        "reachable": True,
        "latencyMs": 50,
        "version": "1.0.0",
        "deployments": [
            {
                "model_name": "gemma3-1b",
                "litellm_params": {"api_base": "http://192.168.1.61:11434"},
            }
        ],
    }
    roster = MF.build_fleet_roster(probe)
    assert roster["nodesHealthy"] >= 1
    assert roster["litellm"]["reachable"] is True


def test_build_fleet_roster_has_required_fields():
    probe = {"reachable": False}
    roster = MF.build_fleet_roster(probe)
    assert "$type" in roster
    assert roster["$type"] == MF.FLEET_COLLECTION
    assert "nodes" in roster
    assert isinstance(roster["nodes"], list)


def test_build_fleet_roster_skips_non_dict_deployment():
    probe = {
        "reachable": True,
        "latencyMs": 10,
        "deployments": ["not-a-dict", 42, None],
    }
    roster = MF.build_fleet_roster(probe)
    assert roster["nodesHealthy"] == 0


# ─── write_fleet_health (with DB mock) ───────────────────────────────────────

def test_write_fleet_health_returns_uri(_stub_db):
    roster = MF.build_fleet_roster({"reachable": False})
    result = MF.write_fleet_health(roster, flush=False)
    assert "uri" in result
    assert result["uri"].startswith("at://")
    assert MF.MURAKUMO_DID in result["uri"]


def test_write_fleet_health_executes_insert(_stub_db):
    roster = MF.build_fleet_roster({"reachable": False})
    MF.write_fleet_health(roster, flush=False)
    assert _stub_db.execute.called


# ─── task_murakumo_fleet_health_check (with DB + probe mock) ─────────────────

def test_task_health_check_with_fake_probe(_stub_db):
    fake_probe = {
        "reachable": False,
        "latencyMs": 5,
        "error": "connection refused",
        "deployments": [],
    }
    with patch.object(MF, "probe_litellm", return_value=fake_probe):
        result = asyncio.run(MF.task_murakumo_fleet_health_check(
            litellmUrl="http://localhost:4000",
            flush=False,
        ))
    assert result["ok"] is True
    assert result["healthPct"] == 0
    assert result["litellmReachable"] is False


def test_task_health_check_reachable_fleet(_stub_db):
    fake_probe = {
        "reachable": True,
        "latencyMs": 20,
        "version": "1.0.0",
        "deployments": [
            {
                "model_name": "gemma3-1b",
                "litellm_params": {"api_base": "http://192.168.1.61:11434"},
            }
        ],
    }
    with patch.object(MF, "probe_litellm", return_value=fake_probe):
        result = asyncio.run(MF.task_murakumo_fleet_health_check(
            litellmUrl="http://localhost:4000",
            flush=False,
        ))
    assert result["ok"] is True
    assert result["litellmReachable"] is True
    assert result["nodesHealthy"] >= 1


# ─── register ────────────────────────────────────────────────────────────────

def test_register_exposes_one_task():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    MF.register(FakeWorker(), timeout_ms=60_000)
    assert registered == ["murakumo.fleet.healthCheck"]
