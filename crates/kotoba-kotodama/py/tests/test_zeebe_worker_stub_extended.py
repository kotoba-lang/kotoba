"""Extended stubs for zeebe_worker_main functions that need additional module stubs.

Covers:
  task_legal_corpus_embed_text  — needs sentence_transformers stub
  task_kouza_sync_due_connections — needs kotodama.handlers.kouza stub
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# ── sentence_transformers stub ───────────────────────────────────────────────
_st_stub = types.ModuleType("sentence_transformers")

class _FakeEmbedding:
    def __init__(self, data):
        self._data = data
    def tolist(self):
        return self._data

class _FakeSentenceTransformer:
    def __init__(self, *a, **kw):
        pass
    def encode(self, text, **kw):
        return _FakeEmbedding([0.1, 0.2, 0.3])

_st_stub.SentenceTransformer = _FakeSentenceTransformer  # type: ignore[attr-defined]
sys.modules.setdefault("sentence_transformers", _st_stub)

# ── kotodama.handlers.kouza stub ───────────────────────────────────────────
_handlers_stub = types.ModuleType("kotodama.handlers")
_kouza_stub = types.ModuleType("kotodama.handlers.kouza")

def _fake_sync_due_connections_payload(params: dict) -> dict:
    return {
        "ok": True,
        "connectionsScanned": 0,
        "syncRunsCreated": 0,
        "syncRunDids": [],
    }

_kouza_stub.sync_due_connections_payload = _fake_sync_due_connections_payload  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.handlers", _handlers_stub)
sys.modules.setdefault("kotodama.handlers.kouza", _kouza_stub)

# ── standard stubs ───────────────────────────────────────────────────────────
_db_stub = types.ModuleType("kotodama.db_sync")

def _noop_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = None
        rowcount = 0
    return _C()

_db_stub.sync_cursor = _noop_cursor  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)

_pyzeebe_stub = types.ModuleType("pyzeebe")
_pyzeebe_stub.ZeebeClient = object  # type: ignore[attr-defined]
_pyzeebe_stub.ZeebeWorker = object  # type: ignore[attr-defined]
_pyzeebe_stub.create_insecure_channel = lambda *a, **kw: None  # type: ignore[attr-defined]
sys.modules.setdefault("pyzeebe", _pyzeebe_stub)

_llm_stub = types.ModuleType("kotodama.llm")
class _LlmError(Exception): pass
_llm_stub.LlmError = _LlmError  # type: ignore[attr-defined]
_llm_stub.call_tier = lambda *a, **kw: {"content": "", "model": "", "usage": {}}  # type: ignore[attr-defined]
_llm_stub.call_tier_json = lambda *a, **kw: {"ok": False, "error": "stub"}  # type: ignore[attr-defined]
_llm_stub.parse_json_content = lambda content: None  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.llm", _llm_stub)

_pkg_stub = types.ModuleType("kotodama")
_pkg_stub.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
_pkg_stub.__package__ = "kotodama"
sys.modules.setdefault("kotodama", _pkg_stub)

# ── load zeebe_worker_main with unique key ────────────────────────────────────
_MOD_NAME = "_zeebe_worker_stub_ext"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "zeebe_worker_main.py"
    real_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
        sys.modules[_MOD_NAME] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        if real_db is not None:
            sys.modules["kotodama.db_sync"] = real_db

Z = sys.modules[_MOD_NAME]


# ─── task_legal_corpus_embed_text — stub model, empty text returns early ──────

def test_legal_corpus_embed_text_empty_text_returns_empty_embedding() -> None:
    result = asyncio.run(Z.task_legal_corpus_embed_text(text=""))
    assert result.get("embedding") == []


def test_legal_corpus_embed_text_empty_text_dim_zero() -> None:
    result = asyncio.run(Z.task_legal_corpus_embed_text(text=""))
    assert result.get("dim") == 0


def test_legal_corpus_embed_text_empty_text_returns_dict() -> None:
    result = asyncio.run(Z.task_legal_corpus_embed_text(text=""))
    assert isinstance(result, dict)


def test_legal_corpus_embed_text_with_text_has_embedding() -> None:
    result = asyncio.run(Z.task_legal_corpus_embed_text(text="test query"))
    assert "embedding" in result


def test_legal_corpus_embed_text_with_text_has_dim() -> None:
    result = asyncio.run(Z.task_legal_corpus_embed_text(text="test query"))
    assert "dim" in result


def test_legal_corpus_embed_text_with_text_dim_matches_embedding() -> None:
    result = asyncio.run(Z.task_legal_corpus_embed_text(text="test query"))
    assert result["dim"] == len(result["embedding"])


# ─── task_kouza_sync_due_connections — stub handler ──────────────────────────

def test_kouza_sync_due_connections_returns_dict() -> None:
    result = asyncio.run(Z.task_kouza_sync_due_connections())
    assert isinstance(result, dict)


def test_kouza_sync_due_connections_has_ok_key() -> None:
    result = asyncio.run(Z.task_kouza_sync_due_connections())
    assert "ok" in result


def test_kouza_sync_due_connections_dry_run_returns_dict() -> None:
    result = asyncio.run(Z.task_kouza_sync_due_connections(dryRun=True))
    assert isinstance(result, dict)
