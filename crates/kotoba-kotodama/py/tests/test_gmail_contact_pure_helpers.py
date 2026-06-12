"""Tests for pure helpers in handlers/gmail_contact.py:
_err, _parse_from, sanitize_path_segment."""

from __future__ import annotations

import json
import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_gmail_contact"
if _MOD_NAME in sys.modules:
    GC = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _nsid in [k for k in list(_reg._HANDLERS.keys()) if "gmail" in k.lower() and "upsert" in k.lower()]:
            del _reg._HANDLERS[_nsid]
    except Exception:
        pass

    def _load_mod(name: str, rel: str) -> types.ModuleType:
        path = _py_src / rel
        spec = importlib.util.spec_from_file_location(name, path)
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    GC = _load_mod(_MOD_NAME, "kotodama/handlers/gmail_contact.py")


# ─── _err ────────────────────────────────────────────────────────────────────

def test_err_returns_json_string() -> None:
    result = GC._err("something went wrong")
    data = json.loads(result)
    assert data["error"] == "something went wrong"


def test_err_includes_extra_kwargs() -> None:
    result = GC._err("fail", code=404, detail="missing")
    data = json.loads(result)
    assert data["code"] == 404
    assert data["detail"] == "missing"


def test_err_empty_message() -> None:
    result = GC._err("")
    data = json.loads(result)
    assert "error" in data


# ─── _parse_from ─────────────────────────────────────────────────────────────

def test_parse_from_simple_email() -> None:
    name, email = GC._parse_from("alice@example.com")
    assert email == "alice@example.com"
    assert name == ""


def test_parse_from_with_display_name() -> None:
    name, email = GC._parse_from('"Alice Smith" <alice@example.com>')
    assert email == "alice@example.com"
    assert name == "Alice Smith"


def test_parse_from_with_bare_display_name() -> None:
    name, email = GC._parse_from("Alice Smith <alice@example.com>")
    assert email == "alice@example.com"
    assert "Alice" in name


def test_parse_from_empty_returns_empty_tuple() -> None:
    name, email = GC._parse_from("")
    assert name == ""
    assert email == ""


def test_parse_from_lowercases_email() -> None:
    _, email = GC._parse_from("ALICE@EXAMPLE.COM")
    assert email == "alice@example.com"


def test_parse_from_strips_whitespace() -> None:
    _, email = GC._parse_from("  alice@example.com  ")
    assert "alice@example.com" in email


def test_parse_from_returns_tuple_of_two() -> None:
    result = GC._parse_from("user@domain.com")
    assert len(result) == 2


def test_parse_from_angle_brackets() -> None:
    _, email = GC._parse_from("<user@domain.com>")
    assert email == "user@domain.com"


# ─── sanitize_path_segment ───────────────────────────────────────────────────

def test_sanitize_simple_email() -> None:
    result = GC.sanitize_path_segment("alice@example.com")
    assert result == "alice-at-example-com"


def test_sanitize_at_symbol_replaced() -> None:
    result = GC.sanitize_path_segment("a@b.com")
    assert "-at-" in result
    assert "@" not in result


def test_sanitize_dots_replaced_with_dash() -> None:
    result = GC.sanitize_path_segment("first.last@example.com")
    assert "." not in result


def test_sanitize_plus_replaced() -> None:
    result = GC.sanitize_path_segment("a+tag@example.com")
    assert "+" not in result


def test_sanitize_underscores_replaced() -> None:
    result = GC.sanitize_path_segment("a_b@example.com")
    assert "_" not in result


def test_sanitize_no_leading_trailing_dashes() -> None:
    result = GC.sanitize_path_segment("alice@example.com")
    assert not result.startswith("-")
    assert not result.endswith("-")


def test_sanitize_no_consecutive_dashes() -> None:
    result = GC.sanitize_path_segment("a..b@example.com")
    assert "--" not in result


def test_sanitize_lowercase_output() -> None:
    result = GC.sanitize_path_segment("ALICE@EXAMPLE.COM")
    assert result == result.lower()


def test_sanitize_max_length_63() -> None:
    long_email = "a" * 50 + "@" + "b" * 50 + ".com"
    result = GC.sanitize_path_segment(long_email)
    assert len(result) <= 63


def test_sanitize_deterministic() -> None:
    email = "test.user+tag@company.co.jp"
    assert GC.sanitize_path_segment(email) == GC.sanitize_path_segment(email)


def test_sanitize_only_alnum_and_dash() -> None:
    result = GC.sanitize_path_segment("alice@example.com")
    import re
    assert re.fullmatch(r"[a-z0-9-]+", result)


def test_sanitize_empty_string_returns_empty_or_dash_stripped() -> None:
    result = GC.sanitize_path_segment("")
    assert isinstance(result, str)
