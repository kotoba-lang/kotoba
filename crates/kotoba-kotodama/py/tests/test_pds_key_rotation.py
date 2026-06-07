"""Unit tests for PDS key rotation Zeebe primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import pds_key_rotation as K  # noqa: E402


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


def test_call_pds_key_rotation_parses_response(monkeypatch):
    monkeypatch.setattr(K, "_http_post_json", lambda url, payload, secret="": {
        "httpStatus": 200,
        "body": {"ok": True, "scanned": 4, "rotated": 3, "errors": [{"did": "did:web:x", "error": "locked"}]},
    })

    out = K.call_pds_key_rotation("https://atproto.example", "secret", 90, 5)

    assert out["ok"] is True
    assert out["scanned"] == 4
    assert out["rotated"] == 3
    assert out["errorCount"] == 1


def test_task_writes_key_rotation_tick(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(K, "sync_cursor", factory)
    monkeypatch.setenv("PDS_SERVICE_AUTH_MINT_SECRET", "secret")
    monkeypatch.setattr(K, "call_pds_key_rotation", lambda _url, _secret, _days, _batch: {
        "ok": True,
        "httpStatus": 200,
        "scanned": 5,
        "rotated": 5,
        "errorCount": 0,
        "errors": [],
        "error": "",
    })

    out = asyncio.run(K.task_pds_signing_keys_rotate_stale(pdsUrl="https://atproto.example"))

    assert out["ok"] is True
    assert out["rotated"] == 5
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:atproto.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.pds.keyRotation"
    value = json.loads(row["value_json"])
    assert value["scanned"] == 5
    assert factory.cursors[0].sqls[-1] == "FLUSH"
