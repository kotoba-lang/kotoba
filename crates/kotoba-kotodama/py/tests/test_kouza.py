"""Unit tests for kotodama.handlers.kouza."""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
import types
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))


if "arrow_udf" not in sys.modules:
    stub = types.ModuleType("arrow_udf")

    def _udf(*a, **k):
        return lambda fn: fn

    stub.udf = _udf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = stub


_src = _P(__file__).resolve().parents[1] / "src/kotodama/handlers/kouza.py"
_spec = _ilu.spec_from_file_location("_kouza_under_test", _src)
K = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(K)  # type: ignore[union-attr]


class _Cursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.sqls = []
        self.params = []

    def execute(self, sql, params=()):
        self.sqls.append(sql)
        self.params.append(params)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return (42,)


class _SyncCursorFactory:
    def __init__(self, rows):
        self.rows = rows
        self.cursors = []

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                cur = _Cursor(factory.rows)
                factory.cursors.append(cur)
                return cur

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_sync_due_connections_dry_run(monkeypatch):
    factory = _SyncCursorFactory([
        ("at://did:web:owner/com.etzhayyim.apps.kouza.institutionConnection/conn-a", "did:web:owner", "mock"),
    ])
    monkeypatch.setattr(K, "sync_cursor", factory)
    monkeypatch.delenv("KOUZA_CORE_URL", raising=False)

    out = K.sync_due_connections_payload({"dryRun": True, "maxConnections": 1, "staleMinutes": 5})

    assert out == {
        "ok": True,
        "dryRun": True,
        "adapterMode": "local-pending",
        "connectionsScanned": 1,
        "syncRunsCreated": 0,
        "syncRunDids": [],
    }
    assert len(factory.cursors) == 1
    assert "vertex_atrecord_kouza_institution_connection" in factory.cursors[0].sqls[0]


def test_sync_due_connections_writes_pending_sync_run(monkeypatch):
    connection_did = "at://did:web:owner/com.etzhayyim.apps.kouza.institutionConnection/conn-a"
    factory = _SyncCursorFactory([(connection_did, "did:web:owner", "mock-provider")])
    monkeypatch.setattr(K, "sync_cursor", factory)
    monkeypatch.delenv("KOUZA_CORE_URL", raising=False)

    out = K.sync_due_connections_payload({"maxConnections": 1, "staleMinutes": 5})

    assert out["ok"] is True
    assert out["connectionsScanned"] == 1
    assert out["syncRunsCreated"] == 1
    assert out["syncRunDids"][0].startswith("at://did:web:owner/com.etzhayyim.apps.kouza.syncRun/")
    write_sql = "\n".join(factory.cursors[1].sqls)
    assert "INSERT INTO vertex_atrecord_kouza_sync_run" in write_sql
    assert "UPDATE vertex_atrecord_kouza_institution_connection" in write_sql
    assert "adapter_pending" in factory.cursors[1].params[1]
    assert "ADAPTER_NOT_CONFIGURED" in factory.cursors[1].params[1]


def test_sync_due_connections_delegates_to_kouza_core(monkeypatch):
    connection_did = "at://did:web:owner/com.etzhayyim.apps.kouza.institutionConnection/conn-a"
    factory = _SyncCursorFactory([(connection_did, "did:web:owner", "mock-provider")])
    monkeypatch.setattr(K, "sync_cursor", factory)
    monkeypatch.setenv("KOUZA_CORE_URL", "https://kouza.etzhayyim.com")

    calls = []

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _limit):
            return b'{"syncRunDid":"at://did:web:owner/com.etzhayyim.apps.kouza.syncRun/sync-core","status":"succeeded"}'

    def _urlopen(req, timeout=0):
        calls.append((req.full_url, req.data, timeout))
        return _Resp()

    monkeypatch.setattr(K.urllib.request, "urlopen", _urlopen)

    out = K.sync_due_connections_payload({"maxConnections": 1, "staleMinutes": 5})

    assert out["ok"] is True
    assert out["adapterMode"] == "kouza-core"
    assert out["syncRunsCreated"] == 1
    assert out["syncRunDids"] == ["at://did:web:owner/com.etzhayyim.apps.kouza.syncRun/sync-core"]
    assert calls[0][0] == "https://kouza.etzhayyim.com/xrpc/com.etzhayyim.apps.kouza.syncConnection"
    assert b'"connectionDid":"at://did:web:owner/com.etzhayyim.apps.kouza.institutionConnection/conn-a"' in calls[0][1]
    assert len(factory.cursors) == 1


def test_kouza_sync_due_connections_envelopes_validation_error():
    out = json.loads(K.kouza_sync_due_connections('{"ownerDid":"not-a-did"}'))
    assert out["ok"] is False
    assert out["connectionsScanned"] == 0
    assert out["syncRunsCreated"] == 0
    assert "ownerDid" in out["error"]
