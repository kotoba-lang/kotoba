"""Unit tests for Murakumo fleet health primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import murakumo_fleet as M  # noqa: E402


class _Cursor:
    def __init__(self):
        self.sqls = []
        self.params = []

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        self.params.append(params)


class _SyncCursorFactory:
    def __init__(self):
        self.cursors = []

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                cur = _Cursor()
                factory.cursors.append(cur)
                return cur

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_build_fleet_roster_maps_litellm_deployments_to_nodes():
    roster = M.build_fleet_roster({
        "reachable": True,
        "latencyMs": 12,
        "version": "1.2.3",
        "deployments": [
            {
                "model_name": "gemma4-e4b",
                "litellm_params": {"api_base": "http://192.168.1.61:11434"},
            }
        ],
    })

    assert roster["healthPct"] == 10
    assert roster["nodesHealthy"] == 1
    assert roster["nodesTotal"] == 10
    assert roster["litellm"]["reachable"] is True
    judah = next(n for n in roster["nodes"] if n["name"] == "judah")
    assert judah["healthy"] is True
    assert judah["model"] == "gemma4-e4b"


def test_task_writes_fleet_health_record(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(M, "sync_cursor", factory)
    monkeypatch.setattr(M, "probe_litellm", lambda _url, _bearer: {
        "reachable": False,
        "latencyMs": 5,
        "error": "down",
        "deployments": [],
    })

    out = asyncio.run(M.task_murakumo_fleet_health_check(litellmUrl="http://litellm"))

    assert out["ok"] is True
    assert out["nodesHealthy"] == 0
    assert out["nodesTotal"] == 10
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:murakumo.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.murakumo.fleetHealth"
    assert json.loads(row["value_json"])["litellm"]["error"] == "down"
    assert factory.cursors[0].sqls[-1] == "FLUSH"
