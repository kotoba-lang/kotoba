"""Tests for playwright handler pure functions and PDS primitive _sign_body."""

from __future__ import annotations

import hashlib
import hmac as _hmac
import importlib.util
import json
import sys
import types
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load_handler(name: str) -> types.ModuleType:
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    mod_name = f"_handler4_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec is not None and spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ─── playwright ──────────────────────────────────────────────────────────────

PW = _load_handler("playwright")


def test_playwright_new_id_format():
    result = PW._new_id("local")
    assert result.startswith("local-")
    suffix = result[len("local-"):]
    assert len(suffix) == 16
    assert all(c in "0123456789abcdef" for c in suffix)


def test_playwright_new_id_is_random():
    assert PW._new_id("cf") != PW._new_id("cf")


def test_session_open_local_target():
    out = json.loads(PW.session_open(json.dumps({"target": "local"})))
    assert out["sessionId"].startswith("local-")
    assert out["target"] == "local"
    assert out["_persisted"] is False
    assert "expiresAt" in out


def test_session_open_cf_browser_target():
    out = json.loads(PW.session_open(json.dumps({"target": "cf-browser"})))
    assert out["sessionId"].startswith("cf-")
    assert out["target"] == "cf-browser"


def test_session_open_default_target_is_local():
    out = json.loads(PW.session_open("{}"))
    assert out["target"] == "local"


def test_session_open_invalid_target_returns_error():
    out = json.loads(PW.session_open(json.dumps({"target": "invalid"})))
    assert "error" in out


def test_session_open_invalid_json_returns_error():
    out = json.loads(PW.session_open("not-json"))
    assert "error" in out


def test_session_open_empty_input_uses_defaults():
    out = json.loads(PW.session_open(""))
    assert out["target"] == "local"
    assert "_persisted" in out


def test_session_close_valid():
    out = json.loads(PW.session_close(json.dumps({"sessionId": "local-abcdef1234567890"})))
    assert out["sessionId"] == "local-abcdef1234567890"
    assert out["closed"] is True
    assert out["_persisted"] is False


def test_session_close_missing_session_id_returns_error():
    out = json.loads(PW.session_close("{}"))
    assert "error" in out
    assert "sessionId" in out["error"]


def test_session_close_invalid_json_returns_error():
    out = json.loads(PW.session_close("not-json"))
    assert "error" in out


# ─── PDS primitive _sign_body shared pattern ─────────────────────────────────

from kotodama.primitives import (  # noqa: E402
    pds_discover_cache as PDC,
    pds_domain_coverage as PDCO,
    pds_key_rotation as PKR,
    pds_mitama_cron as PMC,
    pds_outbox as PO,
    pds_heartbeat as PH,
)


def _expected_sig(secret: str, body: bytes) -> str:
    return _hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_pds_discover_cache_sign_body():
    sig = PDC._sign_body("secret", b"{}")
    assert sig == _expected_sig("secret", b"{}")
    assert len(sig) == 64


def test_pds_domain_coverage_sign_body():
    sig = PDCO._sign_body("key", b"payload")
    assert sig == _expected_sig("key", b"payload")


def test_pds_key_rotation_sign_body():
    sig = PKR._sign_body("key", b"data")
    assert sig == _expected_sig("key", b"data")


def test_pds_mitama_cron_sign_body():
    sig = PMC._sign_body("s3cr3t", b"body")
    assert sig == _expected_sig("s3cr3t", b"body")


def test_pds_outbox_sign_body():
    sig = PO._sign_body("secret", b"{}")
    assert sig == "77325902caca812dc259733aacd046b73817372c777b8d95b402647474516e13"


def test_pds_heartbeat_sign_body():
    sig = PH._sign_body("secret", b"{}")
    assert sig == _expected_sig("secret", b"{}")


def test_sign_body_different_secrets_produce_different_sigs():
    sig1 = PDC._sign_body("key1", b"body")
    sig2 = PDC._sign_body("key2", b"body")
    assert sig1 != sig2


def test_sign_body_different_bodies_produce_different_sigs():
    sig1 = PDC._sign_body("key", b"body1")
    sig2 = PDC._sign_body("key", b"body2")
    assert sig1 != sig2
