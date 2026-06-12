"""Unit tests for graph consumer Zeebe primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import graph_consumer as G  # noqa: E402


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


def test_call_graph_consumer_parses_worker_response(monkeypatch):
    monkeypatch.setattr(G, "_http_post_json", lambda url, payload, bearer="": {
        "httpStatus": 200,
        "body": {"ok": True, "processed": 7, "lastSeq": 123},
    })

    out = G._call_graph_consumer_http("https://graph.example/consume", 50, "tok")

    assert out["ok"] is True
    assert out["processed"] == 7
    assert out["lastSeq"] == 123
    assert out["error"] == ""


def test_task_writes_consume_tick(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(G, "sync_cursor", factory)
    monkeypatch.setattr(G, "_call_graph_consumer_http", lambda _url, _batch_size, _bearer="": {
        "ok": True,
        "httpStatus": 200,
        "processed": 3,
        "lastSeq": 99,
        "error": "",
    })

    out = asyncio.run(G.task_graph_repo_consume_commits(
        consumerUrl="https://graph.example/consume",
        batchSize=50,
    ))

    assert out["ok"] is True
    assert out["processed"] == 3
    assert out["lastSeq"] == 99
    row = factory.cursors[0].params[0]
    assert row["repo"] == "did:web:graph.etzhayyim.com"
    assert row["collection"] == "com.etzhayyim.apps.graph.consumeTick"
    value = json.loads(row["value_json"])
    assert value["processed"] == 3


def test_task_no_url_uses_local_consume_path(monkeypatch):
    monkeypatch.delenv("GRAPH_CONSUMER_URL", raising=False)
    monkeypatch.delenv("GRAPH_WORKER_CONSUME_URL", raising=False)
    monkeypatch.setattr(G, "_consume_commits_local", lambda batch_size=50: {
        "ok": True, "processed": 0, "lastSeq": 0,
    })
    factory = _SyncCursorFactory()
    monkeypatch.setattr(G, "sync_cursor", factory)

    out = asyncio.run(G.task_graph_repo_consume_commits())

    assert out["ok"] is True
    assert out["processed"] == 0
