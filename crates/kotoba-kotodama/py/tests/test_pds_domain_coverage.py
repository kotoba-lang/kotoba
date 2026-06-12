"""Unit tests for PDS domain coverage primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import pds_domain_coverage as D  # noqa: E402


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


def test_call_pds_domain_coverage_expand_parses_response(monkeypatch):
    monkeypatch.setattr(D, "_http_post_json", lambda url, payload, secret="": {
        "httpStatus": 200,
        "body": {
            "ok": True,
            "domain": "example.com",
            "appDid": "did:web:example-com.etzhayyim.com",
            "knowledgeEdges": 3,
            "postWritten": True,
        },
    })

    out = D.call_pds_domain_coverage_expand("https://atproto.example", "secret")

    assert out["ok"] is True
    assert out["domain"] == "example.com"
    assert out["appDid"] == "did:web:example-com.etzhayyim.com"
    assert out["knowledgeEdges"] == 3
    assert out["postWritten"] is True


def test_task_writes_domain_coverage_tick(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(D, "sync_cursor", factory)
    monkeypatch.setenv("PDS_SERVICE_AUTH_MINT_SECRET", "secret")
    monkeypatch.setattr(D, "call_pds_domain_coverage_expand", lambda _url, _secret: {
        "ok": True,
        "httpStatus": 200,
        "domain": "example.com",
        "appDid": "did:web:example-com.etzhayyim.com",
        "knowledgeEdges": 2,
        "postWritten": True,
        "error": "",
    })

    out = asyncio.run(D.task_pds_domain_coverage_expand(pdsUrl="https://atproto.example"))

    assert out["ok"] is True
    assert out["domain"] == "example.com"
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:atproto.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.pds.domainCoverageExpansion"
    value = json.loads(row["value_json"])
    assert value["appDid"] == "did:web:example-com.etzhayyim.com"
    assert value["postWritten"] is True
    assert factory.cursors[0].sqls[-1] == "FLUSH"
