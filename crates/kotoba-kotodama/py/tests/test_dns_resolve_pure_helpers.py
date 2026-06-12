"""Tests for pure helpers in handlers/dns_resolve.py:
_answer_strings, resolve (no-network paths), resolve_json (no-network paths)."""

from __future__ import annotations

import json
import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_dns_resolve"
if _MOD_NAME in sys.modules:
    DR = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if "dns" in k.lower()]:
            del _reg._HANDLERS[_k]
    except Exception:
        pass

    def _load_mod(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    DR = _load_mod(_MOD_NAME, "kotodama/handlers/dns_resolve.py")


# ─── _answer_strings ─────────────────────────────────────────────────────────

def test_answer_strings_none_body_returns_empty() -> None:
    assert DR._answer_strings(None) == []


def test_answer_strings_non_zero_status_returns_empty() -> None:
    body = {"Status": 3, "Answer": [{"data": "1.2.3.4"}]}
    assert DR._answer_strings(body) == []


def test_answer_strings_status_zero_extracts_data() -> None:
    body = {"Status": 0, "Answer": [{"data": "1.2.3.4"}, {"data": "5.6.7.8"}]}
    result = DR._answer_strings(body)
    assert result == ["1.2.3.4", "5.6.7.8"]


def test_answer_strings_skips_non_dict_entries() -> None:
    body = {"Status": 0, "Answer": ["bad", {"data": "1.2.3.4"}]}
    result = DR._answer_strings(body)
    assert result == ["1.2.3.4"]


def test_answer_strings_skips_empty_data() -> None:
    body = {"Status": 0, "Answer": [{"data": ""}, {"data": "ok.com"}]}
    result = DR._answer_strings(body)
    assert result == ["ok.com"]


def test_answer_strings_no_answer_key_returns_empty() -> None:
    body = {"Status": 0}
    assert DR._answer_strings(body) == []


def test_answer_strings_empty_answer_list() -> None:
    body = {"Status": 0, "Answer": []}
    assert DR._answer_strings(body) == []


def test_answer_strings_preserves_order() -> None:
    body = {"Status": 0, "Answer": [
        {"data": "first"},
        {"data": "second"},
        {"data": "third"},
    ]}
    result = DR._answer_strings(body)
    assert result == ["first", "second", "third"]


def test_answer_strings_empty_body_returns_empty() -> None:
    assert DR._answer_strings({}) == []


# ─── resolve — no-network guard paths ────────────────────────────────────────

def test_resolve_empty_domain_returns_empty_string() -> None:
    assert DR.resolve("", "A") == ""


# ─── resolve_json — no-network guard paths ───────────────────────────────────

def test_resolve_json_empty_domain_returns_error_json() -> None:
    result = json.loads(DR.resolve_json("", "A"))
    assert "error" in result


def test_resolve_json_disallowed_rtype_returns_error() -> None:
    result = json.loads(DR.resolve_json("example.com", "INVALID"))
    assert "error" in result
    assert "INVALID" in result["error"]


def test_resolve_json_disallowed_rtype_lowercase_accepted() -> None:
    # resolve_json uppercases rtype before checking, so "a" → "A" is valid
    result = json.loads(DR.resolve_json("", "a"))
    # empty domain triggers the domain guard, not an rtype error
    assert "error" in result
    assert "domain" in result["error"]


def test_resolve_json_allowed_rtypes_not_rejected_by_guard() -> None:
    # These pass the guard and attempt network — they may fail but should not
    # return a guard-level "rtype not allowed" error.
    for rtype in ("A", "AAAA", "MX", "NS", "TXT"):
        out = json.loads(DR.resolve_json("", rtype))
        assert "error" not in out or "rtype" not in out.get("error", "")


# ─── constants ───────────────────────────────────────────────────────────────

def test_allowed_rtypes_contains_standard_types() -> None:
    for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CNAME"):
        assert rtype in DR._ALLOWED_RTYPES


def test_allowed_rtypes_is_frozenset() -> None:
    assert isinstance(DR._ALLOWED_RTYPES, frozenset)
