"""Unit tests for PDS Mitama cron-trigger resync primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import pds_mitama_cron as M  # noqa: E402


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


def test_call_pds_mitama_cron_resync_parses_response(monkeypatch):
    monkeypatch.setattr(M, "_http_post_json", lambda url, payload, secret="": {
        "httpStatus": 200,
        "body": {"ok": True, "scheduled": 7},
    })

    out = M.call_pds_mitama_cron_resync("https://atproto.example", "secret")

    assert out["ok"] is True
    assert out["scheduled"] == 7


def test_task_writes_mitama_cron_resync_tick(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(M, "sync_cursor", factory)
    monkeypatch.setenv("PDS_SERVICE_AUTH_MINT_SECRET", "secret")
    monkeypatch.setattr(M, "call_pds_mitama_cron_resync", lambda _url, _secret: {
        "ok": True,
        "httpStatus": 200,
        "scheduled": 4,
        "error": "",
    })

    out = asyncio.run(M.task_pds_mitama_cron_triggers_resync(pdsUrl="https://atproto.example"))

    assert out["ok"] is True
    assert out["scheduled"] == 4
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:atproto.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.pds.mitamaCronResync"
    value = json.loads(row["value_json"])
    assert value["scheduled"] == 4
    assert factory.cursors[0].sqls[-1] == "FLUSH"
