"""Tests for pure computation in handlers/playwright.py.

session_open and session_close are purely synchronous JSON transforms —
no DB, no network, no subprocess. All paths are testable without mocks.

Uses a unique module-load key to avoid NSID double-registration when
test_playwright_pds_sign.py is collected in the same pytest session.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf decorator is a no-op (avoids NSID registry clashes)
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load_handler(name: str) -> types.ModuleType:
    # Use the same module-name key as test_playwright_pds_sign.py so both
    # files share one instance (avoids duplicate NSID registration).
    mod_name = f"_handler4_{name}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


PW = _load_handler("playwright")


# ─── _new_id ─────────────────────────────────────────────────────────────────

def test_new_id_contains_prefix() -> None:
    result = PW._new_id("local")
    assert result.startswith("local-")


def test_new_id_has_hex_suffix() -> None:
    result = PW._new_id("cf")
    suffix = result.split("-", 1)[1]
    assert len(suffix) == 16
    assert all(c in "0123456789abcdef" for c in suffix)


def test_new_id_is_different_each_call() -> None:
    a = PW._new_id("x")
    b = PW._new_id("x")
    assert a != b


def test_new_id_custom_prefix() -> None:
    result = PW._new_id("session")
    assert result.startswith("session-")


# ─── session_open ─────────────────────────────────────────────────────────────

def test_session_open_local_default() -> None:
    out = json.loads(PW.session_open("{}"))
    assert out["target"] == "local"
    assert "sessionId" in out
    assert out["_persisted"] is False


def test_session_open_local_has_expires_at() -> None:
    out = json.loads(PW.session_open("{}"))
    assert "expiresAt" in out
    assert out["expiresAt"].endswith("+00:00")


def test_session_open_local_session_id_prefix() -> None:
    out = json.loads(PW.session_open('{"target": "local"}'))
    assert out["sessionId"].startswith("local-")


def test_session_open_cf_browser() -> None:
    out = json.loads(PW.session_open('{"target": "cf-browser"}'))
    assert out["target"] == "cf-browser"
    assert out["sessionId"].startswith("cf-")


def test_session_open_empty_string_defaults_to_local() -> None:
    out = json.loads(PW.session_open(""))
    assert out["target"] == "local"


def test_session_open_invalid_json_returns_error() -> None:
    out = json.loads(PW.session_open("not json {"))
    assert "error" in out


def test_session_open_wrong_target_returns_error() -> None:
    out = json.loads(PW.session_open('{"target": "safari"}'))
    assert "error" in out
    assert "target" in out["error"]


def test_session_open_returns_json_string() -> None:
    result = PW.session_open("{}")
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_session_open_local_ttl_longer_than_cf() -> None:
    import datetime
    local_out = json.loads(PW.session_open('{"target": "local"}'))
    cf_out = json.loads(PW.session_open('{"target": "cf-browser"}'))
    local_exp = datetime.datetime.fromisoformat(local_out["expiresAt"])
    cf_exp = datetime.datetime.fromisoformat(cf_out["expiresAt"])
    assert local_exp > cf_exp


def test_session_open_null_target_defaults_to_local() -> None:
    out = json.loads(PW.session_open('{"target": null}'))
    assert out["target"] == "local"


# ─── session_close ────────────────────────────────────────────────────────────

def test_session_close_returns_closed_true() -> None:
    out = json.loads(PW.session_close('{"sessionId": "local-abc123"}'))
    assert out["closed"] is True


def test_session_close_echoes_session_id() -> None:
    out = json.loads(PW.session_close('{"sessionId": "my-session-id"}'))
    assert out["sessionId"] == "my-session-id"


def test_session_close_persisted_false() -> None:
    out = json.loads(PW.session_close('{"sessionId": "s1"}'))
    assert out["_persisted"] is False


def test_session_close_missing_session_id_returns_error() -> None:
    out = json.loads(PW.session_close("{}"))
    assert "error" in out
    assert "sessionId" in out["error"]


def test_session_close_empty_session_id_returns_error() -> None:
    out = json.loads(PW.session_close('{"sessionId": ""}'))
    assert "error" in out


def test_session_close_invalid_json_returns_error() -> None:
    out = json.loads(PW.session_close("bad json"))
    assert "error" in out


def test_session_close_empty_input_returns_error() -> None:
    out = json.loads(PW.session_close(""))
    assert "error" in out


def test_session_close_returns_json_string() -> None:
    result = PW.session_close('{"sessionId": "abc"}')
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
