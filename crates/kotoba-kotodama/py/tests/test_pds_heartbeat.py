"""Unit tests for PDS heartbeat Zeebe primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import pds_heartbeat as H  # noqa: E402


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


def test_call_pds_heartbeat_parses_response(monkeypatch):
    monkeypatch.setattr(H, "_http_post_json", lambda url, payload, secret="": {
        "httpStatus": 200,
        "body": {"ok": True, "appsTotal": 10, "batchIndex": 2, "batchSize": 2, "heartbeatOk": 2, "heartbeatFail": 0, "shinkaStatus": 200},
    })

    out = H.call_pds_heartbeat("https://atproto.example", "secret")

    assert out["ok"] is True
    assert out["heartbeatOk"] == 2
    assert out["shinkaStatus"] == 200


def test_task_writes_heartbeat_tick(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(H, "sync_cursor", factory)
    monkeypatch.setenv("PDS_SERVICE_AUTH_MINT_SECRET", "secret")
    monkeypatch.setattr(H, "call_pds_heartbeat", lambda _url, _secret: {
        "ok": True,
        "httpStatus": 200,
        "appsTotal": 12,
        "batchIndex": 1,
        "batchSize": 3,
        "heartbeatOk": 2,
        "heartbeatFail": 1,
        "shinkaStatus": 200,
        "error": "",
    })

    out = asyncio.run(H.task_pds_heartbeat_run(pdsUrl="https://atproto.example"))

    assert out["ok"] is True
    assert out["heartbeatFail"] == 1
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:atproto.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.pds.heartbeatCron"
    value = json.loads(row["value_json"])
    assert value["appsTotal"] == 12
    assert factory.cursors[0].sqls[-1] == "FLUSH"
