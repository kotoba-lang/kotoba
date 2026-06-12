"""Unit tests for kotoba-kotodama organizer Zeebe primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import kotoba-kotodama_organizer as M  # noqa: E402


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


def test_call_organizer_summarizes_plan(monkeypatch):
    monkeypatch.setattr(M, "_http_post_json", lambda url, payload, bearer="": {
        "httpStatus": 200,
        "body": {
            "ts": "2026-04-25T00:00:00Z",
            "runsTotal24h": 12,
            "summary": {"hot": 1, "normal": 2, "stale": 3, "silent": 4, "archived": 5},
            "fleet": {"saturation": 0.42},
        },
    })

    out = M.call_organizer("https://kotoba-kotodama.example/api/organizer/run", "tok")

    assert out["ok"] is True
    assert out["runsTotal24h"] == 12
    assert out["summary"]["stale"] == 3
    assert out["fleetSaturation"] == 0.42


def test_task_writes_organizer_run(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(M, "sync_cursor", factory)
    monkeypatch.setattr(M, "call_organizer", lambda _url, _bearer="": {
        "ok": True,
        "httpStatus": 200,
        "runsTotal24h": 8,
        "summary": {"hot": 1, "normal": 7, "stale": 0, "silent": 0, "archived": 0},
        "fleetSaturation": 0.2,
        "planTs": "2026-04-25T00:00:00Z",
        "error": "",
    })

    out = asyncio.run(M.task_kotoba-kotodama_organizer_run(
        organizerUrl="https://kotoba-kotodama.example/api/organizer/run",
    ))

    assert out["ok"] is True
    assert out["runsTotal24h"] == 8
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:kotoba-kotodama.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.kotoba-kotodama.organizerRun"
    value = json.loads(row["value_json"])
    assert value["summary"]["normal"] == 7
    assert factory.cursors[0].sqls[-1] == "FLUSH"


def test_task_requires_organizer_url(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(M, "sync_cursor", factory)
    monkeypatch.delenv("KOTODAMA_ORGANIZER_URL", raising=False)

    out = asyncio.run(M.task_kotoba-kotodama_organizer_run())

    assert out["ok"] is False
    assert "KOTODAMA_ORGANIZER_URL" in out["error"]
