"""
Unit tests for the DoH resolver UDF
(kotodama.handlers.dns_resolve).

Pure-function coverage (no live network):
- `_answer_strings` extracts `Answer[*].data` from a DoH JSON body and
  ignores non-NOERROR responses, missing Answer sections, and non-dict
  entries.
- `_doh_fetch` rejects empty domain / disallowed rtype.
- `resolve` / `resolve_json` reject empty input early (no HTTP call).

Live-network behaviour (resolve('etzhayyim.com','A') against Cloudflare DoH)
is covered by the integration suite so this file stays offline-safe.
"""

from __future__ import annotations

import json
import sys
import types

# Stub arrow_udf so kotodama.registry imports cleanly without the
# runtime dependency (same pattern as test_tls_probe.py).
if "arrow_udf" not in sys.modules:
    stub = types.ModuleType("arrow_udf")

    def _udf(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap

    stub.udf = _udf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = stub

# Import the leaf module directly via importlib, NOT via
# `kotodama.handlers` — that package's __init__.py eagerly loads
# langgraph (via the shinka handler) which isn't available in the
# test venv. Going straight to the file avoids the transitive deps.
import importlib.util as _ilu  # noqa: E402
from pathlib import Path as _P  # noqa: E402

_src = _P(__file__).resolve().parents[1] / "src/kotodama/handlers/dns_resolve.py"
_spec = _ilu.spec_from_file_location("_dns_resolve_under_test", _src)
D = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(D)  # type: ignore[union-attr]


# ─── _answer_strings ────────────────────────────────────────────────────


def test_answer_strings_happy():
    body = {"Status": 0, "Answer": [
        {"name": "etzhayyim.com", "type": 1, "TTL": 60, "data": "104.21.25.30"},
        {"name": "etzhayyim.com", "type": 1, "TTL": 60, "data": "172.67.222.17"},
    ]}
    assert D._answer_strings(body) == ["104.21.25.30", "172.67.222.17"]


def test_answer_strings_skips_nxdomain():
    # Status 3 = NXDOMAIN
    body = {"Status": 3, "Answer": [{"data": "ignored"}]}
    assert D._answer_strings(body) == []


def test_answer_strings_ignores_non_dict_entries():
    body = {"Status": 0, "Answer": [{"data": "ok"}, "bogus", None, {"data": ""}]}
    assert D._answer_strings(body) == ["ok"]


def test_answer_strings_missing_answer():
    assert D._answer_strings({"Status": 0}) == []


def test_answer_strings_empty_body():
    assert D._answer_strings(None) == []
    assert D._answer_strings({}) == []


# ─── _doh_fetch input guards ────────────────────────────────────────────


def test_doh_fetch_rejects_empty_domain():
    assert D._doh_fetch("", "A") is None


def test_doh_fetch_rejects_unknown_rtype():
    assert D._doh_fetch("etzhayyim.com", "XYZ") is None
    assert D._doh_fetch("etzhayyim.com", "") is None


# ─── resolve / resolve_json early-return shape ─────────────────────────


def test_resolve_empty_domain_no_fetch(monkeypatch):
    # Patch _doh_fetch so a call would raise — prove we never reach it.
    def _boom(*args, **kw):
        raise AssertionError("should not fetch for empty domain")
    monkeypatch.setattr(D, "_doh_fetch", _boom)
    assert D.resolve("", "A") == ""


def test_resolve_bad_rtype(monkeypatch):
    called = []
    monkeypatch.setattr(D, "_doh_fetch", lambda *a, **kw: called.append(a) or None)
    # Unknown rtype causes _doh_fetch to short-circuit (returns None) and
    # the result is an empty string.
    assert D.resolve("etzhayyim.com", "XYZ") == ""


def test_resolve_joins_answers(monkeypatch):
    monkeypatch.setattr(D, "_doh_fetch", lambda d, r: {
        "Status": 0,
        "Answer": [{"data": "a"}, {"data": "b"}],
    })
    assert D.resolve("x", "A") == "a,b"


def test_resolve_json_empty_domain(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("should not fetch for empty domain")
    monkeypatch.setattr(D, "_doh_fetch", _boom)
    out = json.loads(D.resolve_json("", "A"))
    assert out == {"error": "domain required"}


def test_resolve_json_bad_rtype():
    out = json.loads(D.resolve_json("etzhayyim.com", "XYZ"))
    assert out["error"].startswith("rtype not allowed")


def test_resolve_json_fetch_failure(monkeypatch):
    monkeypatch.setattr(D, "_doh_fetch", lambda d, r: None)
    out = json.loads(D.resolve_json("etzhayyim.com", "A"))
    assert out == {"error": "fetch failed", "domain": "etzhayyim.com", "rtype": "A"}


def test_resolve_json_roundtrip(monkeypatch):
    body = {"Status": 0, "Answer": [{"data": "1.2.3.4", "TTL": 60}]}
    monkeypatch.setattr(D, "_doh_fetch", lambda d, r: body)
    out = json.loads(D.resolve_json("etzhayyim.com", "A"))
    assert out == body
