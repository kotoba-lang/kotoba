"""Tests for pure helper functions in vector_embedding.py and pds_domain_coverage.py."""

from __future__ import annotations

import math
import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import vector_embedding as VE
from kotodama.primitives import pds_domain_coverage as DC

# ── load vector_embedding_ops (has pyzeebe/aiohttp deps) ─────────────────────

def _vstub(name: str, **attrs: object) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


_vstub("kotodama.ingest.zeebe", start_process_if_configured=lambda *a, **kw: None)

_VEO_MOD = "_veo_ops"
if _VEO_MOD not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _VEO_MOD, _py_src / "kotodama" / "vector_embedding_ops.py"
    )
    _m = types.ModuleType(_VEO_MOD)
    _m.__file__ = str(_py_src / "kotodama" / "vector_embedding_ops.py")
    sys.modules[_VEO_MOD] = _m
    _spec.loader.exec_module(_m)  # type: ignore[union-attr]

VEO = sys.modules[_VEO_MOD]


# ─── vector_embedding_ops._json_default ──────────────────────────────────────

def test_veo_json_default_none_returns_string() -> None:
    result = VEO._json_default(None)
    assert result == "None"


def test_veo_json_default_int_returns_string() -> None:
    result = VEO._json_default(42)
    assert result == "42"


def test_veo_json_default_float_returns_string() -> None:
    result = VEO._json_default(3.14)
    assert "3.14" in result


def test_veo_json_default_list_returns_string() -> None:
    result = VEO._json_default([1, 2, 3])
    assert isinstance(result, str)
    assert "1" in result


def test_veo_json_default_dict_returns_string() -> None:
    result = VEO._json_default({"key": "val"})
    assert isinstance(result, str)


def test_veo_json_default_returns_str_type() -> None:
    assert isinstance(VEO._json_default(object()), str)


# ─── vector_embedding: _clean_text ───────────────────────────────────────────

def test_clean_text_collapses_whitespace() -> None:
    assert VE._clean_text("hello  world") == "hello world"


def test_clean_text_strips_leading_trailing() -> None:
    assert VE._clean_text("  hello  ") == "hello"


def test_clean_text_none_returns_empty() -> None:
    assert VE._clean_text(None) == ""


def test_clean_text_truncates_at_limit() -> None:
    long_text = "a " * 3000
    result = VE._clean_text(long_text, limit=10)
    assert len(result) <= 10


def test_clean_text_collapses_newlines() -> None:
    result = VE._clean_text("line1\nline2\ntabs\there")
    assert "\n" not in result


# ─── vector_embedding: _actor_text ───────────────────────────────────────────

def test_actor_text_combines_fields() -> None:
    row = {"display_name": "Alice", "handle": "alice.etzhayyim.com", "description": "A bot"}
    result = VE._actor_text(row)
    assert "Alice" in result
    assert "alice.etzhayyim.com" in result
    assert "A bot" in result


def test_actor_text_missing_fields_graceful() -> None:
    result = VE._actor_text({})
    assert isinstance(result, str)


def test_actor_text_none_fields_not_in_output() -> None:
    row = {"display_name": "Bob", "handle": None}
    result = VE._actor_text(row)
    assert "Bob" in result
    assert "None" not in result


# ─── vector_embedding: _post_text ────────────────────────────────────────────

def test_post_text_combines_text_fields() -> None:
    row = {"text": "Hello world", "handle": "user.etzhayyim.com"}
    result = VE._post_text(row)
    assert "Hello world" in result
    assert "user.etzhayyim.com" in result


def test_post_text_empty_row() -> None:
    result = VE._post_text({})
    assert isinstance(result, str)


# ─── vector_embedding: normalize_768 ─────────────────────────────────────────

def test_normalize_768_length() -> None:
    vec = [1.0] * VE.DIM
    result = VE.normalize_768(vec)
    assert len(result) == VE.DIM


def test_normalize_768_unit_norm() -> None:
    vec = [1.0] * VE.DIM
    result = VE.normalize_768(vec)
    norm = math.sqrt(sum(v * v for v in result))
    assert abs(norm - 1.0) < 1e-6


def test_normalize_768_pads_short_vector() -> None:
    short = [1.0, 0.0]
    result = VE.normalize_768(short)
    assert len(result) == VE.DIM
    # first element should be 1.0 (only non-zero), rest 0.0
    assert abs(result[0] - 1.0) < 1e-6


def test_normalize_768_truncates_long_vector() -> None:
    long = [1.0] * (VE.DIM + 100)
    result = VE.normalize_768(long)
    assert len(result) == VE.DIM


def test_normalize_768_zero_norm_raises() -> None:
    try:
        VE.normalize_768([0.0] * VE.DIM)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ─── vector_embedding: vector_literal ────────────────────────────────────────

def test_vector_literal_is_string() -> None:
    vec = [0.0] * (VE.DIM - 1) + [1.0]
    result = VE.vector_literal(vec)
    assert isinstance(result, str)
    assert result.startswith("[")
    assert result.endswith("]")


def test_vector_literal_contains_floats() -> None:
    vec = [0.0] * (VE.DIM - 1) + [1.0]
    result = VE.vector_literal(vec)
    parts = result[1:-1].split(",")
    assert len(parts) == VE.DIM


# ─── vector_embedding: _fake_embed ───────────────────────────────────────────

def test_fake_embed_returns_list_of_lists() -> None:
    result = VE._fake_embed(["hello", "world"])
    assert len(result) == 2
    assert all(len(v) == VE.DIM for v in result)


def test_fake_embed_deterministic() -> None:
    a = VE._fake_embed(["test string"])
    b = VE._fake_embed(["test string"])
    assert a == b


def test_fake_embed_different_inputs_different_output() -> None:
    a = VE._fake_embed(["text a"])
    b = VE._fake_embed(["text b"])
    assert a != b


def test_fake_embed_vectors_unit_norm() -> None:
    result = VE._fake_embed(["hello"])
    vec = result[0]
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-6


def test_fake_embed_empty_list() -> None:
    assert VE._fake_embed([]) == []


# ─── pds_domain_coverage: _sign_body ─────────────────────────────────────────

def test_sign_body_deterministic() -> None:
    a = DC._sign_body("secret", b"payload")
    b = DC._sign_body("secret", b"payload")
    assert a == b


def test_sign_body_length() -> None:
    sig = DC._sign_body("secret", b"data")
    assert len(sig) == 64  # SHA-256 hex = 64 chars


def test_sign_body_varies_with_secret() -> None:
    a = DC._sign_body("secret1", b"data")
    b = DC._sign_body("secret2", b"data")
    assert a != b


def test_sign_body_varies_with_payload() -> None:
    a = DC._sign_body("secret", b"payload-a")
    b = DC._sign_body("secret", b"payload-b")
    assert a != b


# ─── _hume_enabled / _hume_fake_enabled ──────────────────────────────────────

import os as _os


def test_hume_enabled_false_by_default() -> None:
    _os.environ.pop("VECTOR_EMBEDDING_HUME", None)
    assert VE._hume_enabled() is False


def test_hume_enabled_true_when_set_1() -> None:
    _os.environ["VECTOR_EMBEDDING_HUME"] = "1"
    try:
        assert VE._hume_enabled() is True
    finally:
        del _os.environ["VECTOR_EMBEDDING_HUME"]


def test_hume_enabled_true_when_set_true() -> None:
    _os.environ["VECTOR_EMBEDDING_HUME"] = "true"
    try:
        assert VE._hume_enabled() is True
    finally:
        del _os.environ["VECTOR_EMBEDDING_HUME"]


def test_hume_enabled_false_when_set_0() -> None:
    _os.environ["VECTOR_EMBEDDING_HUME"] = "0"
    try:
        assert VE._hume_enabled() is False
    finally:
        del _os.environ["VECTOR_EMBEDDING_HUME"]


def test_hume_fake_enabled_false_by_default() -> None:
    _os.environ.pop("VECTOR_EMBEDDING_HUME_FAKE", None)
    assert VE._hume_fake_enabled() is False


def test_hume_fake_enabled_true_when_set_yes() -> None:
    _os.environ["VECTOR_EMBEDDING_HUME_FAKE"] = "yes"
    try:
        assert VE._hume_fake_enabled() is True
    finally:
        del _os.environ["VECTOR_EMBEDDING_HUME_FAKE"]


def test_hume_fake_enabled_true_when_set_on() -> None:
    _os.environ["VECTOR_EMBEDDING_HUME_FAKE"] = "on"
    try:
        assert VE._hume_fake_enabled() is True
    finally:
        del _os.environ["VECTOR_EMBEDDING_HUME_FAKE"]


# ─── _row_dicts ──────────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, cols: list[str], rows: list[tuple]) -> None:
        self.description = [(c,) for c in cols]
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return self._rows


def test_row_dicts_basic() -> None:
    cur = _FakeCursor(["id", "name"], [(1, "Alice"), (2, "Bob")])
    result = VE._row_dicts(cur)
    assert result == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]


def test_row_dicts_empty_rows() -> None:
    cur = _FakeCursor(["id", "name"], [])
    assert VE._row_dicts(cur) == []


def test_row_dicts_no_description() -> None:
    class _NoCols:
        description = None
        def fetchall(self): return []
    assert VE._row_dicts(_NoCols()) == []


# ─── vector_embedding_ops._parse_args ────────────────────────────────────────

import sys as _sys


def test_veo_parse_args_deploy_command(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "deploy", "--bpmn", "foo.bpmn"])
    args = VEO._parse_args()
    assert args.command == "deploy"
    assert args.bpmn == "foo.bpmn"


def test_veo_parse_args_start_actors(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "actors"])
    args = VEO._parse_args()
    assert args.command == "start"
    assert args.surface == "actors"


def test_veo_parse_args_start_posts(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "posts"])
    args = VEO._parse_args()
    assert args.surface == "posts"


def test_veo_parse_args_start_limit_default(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "actors"])
    args = VEO._parse_args()
    assert args.limit == 100


def test_veo_parse_args_start_custom_limit(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "actors", "--limit", "50"])
    args = VEO._parse_args()
    assert args.limit == 50


def test_veo_parse_args_start_dry_run_default_false(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "actors"])
    args = VEO._parse_args()
    assert args.dry_run is False


def test_veo_parse_args_start_dry_run_flag(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "actors", "--dry-run"])
    args = VEO._parse_args()
    assert args.dry_run is True


def test_veo_parse_args_start_shard_id_default(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "actors"])
    args = VEO._parse_args()
    assert args.shard_id == -1


def test_veo_parse_args_deploy_tenant_id(monkeypatch) -> None:
    monkeypatch.setattr(_sys, "argv", ["prog", "deploy", "--bpmn", "f.bpmn", "--tenant-id", "t1"])
    args = VEO._parse_args()
    assert args.tenant_id == "t1"


def test_veo_parse_args_returns_namespace(monkeypatch) -> None:
    import argparse
    monkeypatch.setattr(_sys, "argv", ["prog", "start", "--surface", "actors"])
    args = VEO._parse_args()
    assert isinstance(args, argparse.Namespace)
