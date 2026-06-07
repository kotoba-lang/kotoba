"""Unit tests for PDS write-outbox Zeebe primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import pds_outbox as P  # noqa: E402


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


def test_sign_body_matches_hmac_sha256():
    assert P._sign_body("secret", b"{}") == "77325902caca812dc259733aacd046b73817372c777b8d95b402647474516e13"


def test_call_pds_outbox_sync_parses_response(monkeypatch):
    monkeypatch.setattr(P, "_http_post_json", lambda url, payload, secret="": {
        "httpStatus": 200,
        "body": {"ok": True, "replayed": 2, "retried": 1, "expired": 0},
    })

    out = P.call_pds_outbox_sync("https://atproto.example", "secret")

    assert out["ok"] is True
    assert out["replayed"] == 2
    assert out["retried"] == 1
    assert out["expired"] == 0


def test_task_writes_outbox_sync_tick(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(P, "sync_cursor", factory)
    monkeypatch.setenv("PDS_SERVICE_AUTH_MINT_SECRET", "secret")
    monkeypatch.setattr(P, "call_pds_outbox_sync", lambda _url, _secret: {
        "ok": True,
        "httpStatus": 200,
        "replayed": 3,
        "retried": 0,
        "expired": 1,
        "error": "",
    })

    out = asyncio.run(P.task_pds_write_outbox_sync(pdsUrl="https://atproto.example"))

    assert out["ok"] is True
    assert out["replayed"] == 3
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:atproto.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.pds.writeOutboxSync"
    value = json.loads(row["value_json"])
    assert value["expired"] == 1
    assert factory.cursors[0].sqls[-1] == "FLUSH"
