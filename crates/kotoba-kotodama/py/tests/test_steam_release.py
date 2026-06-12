"""
Unit tests for kotodama.handlers.steam_release.

Pure-function coverage (no live network):
- `_parse_date` handles the four common Steam date formats + a year-only
  fallback + returns (None, None) for garbage.
- `release_date` envelopes empty appid, fetch failure, success=False,
  and coming_soon without reaching the network.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
import types
from pathlib import Path as _P


if "arrow_udf" not in sys.modules:
    stub = types.ModuleType("arrow_udf")

    def _udf(*a, **k):
        return lambda fn: fn

    stub.udf = _udf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = stub


_src = _P(__file__).resolve().parents[1] / "src/kotodama/handlers/steam_release.py"
_spec = _ilu.spec_from_file_location("_steam_under_test", _src)
S = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(S)  # type: ignore[union-attr]


# ─── _parse_date ────────────────────────────────────────────────────────


def test_parse_date_dd_mon_yyyy():
    assert S._parse_date("10 Aug, 2021") == ("2021-08-10", 2021)


def test_parse_date_mon_dd_yyyy():
    assert S._parse_date("Aug 10, 2021") == ("2021-08-10", 2021)


def test_parse_date_year_only_fallback():
    # Steam often shows "Q4 2026" / "2026" for unreleased titles
    assert S._parse_date("Q4 2026") == ("2026-01-01", 2026)
    assert S._parse_date("2026") == ("2026-01-01", 2026)


def test_parse_date_garbage():
    assert S._parse_date("coming soon") == (None, None)


def test_parse_date_empty():
    assert S._parse_date("") == (None, None)
    assert S._parse_date(None) == (None, None)  # type: ignore[arg-type]


# ─── release_date envelopes ────────────────────────────────────────────


def test_release_date_empty_appid(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("should not fetch for empty appid")
    monkeypatch.setattr(S, "_fetch", _boom)
    out = json.loads(S.release_date(""))
    assert out["releaseDate"] is None and out["reason"] == "appid required"


def test_release_date_fetch_failure(monkeypatch):
    monkeypatch.setattr(S, "_fetch", lambda a: None)
    out = json.loads(S.release_date("123"))
    assert out == {"appid": "123", "releaseDate": None, "reason": "fetch failed"}


def test_release_date_not_success(monkeypatch):
    monkeypatch.setattr(S, "_fetch", lambda a: {"123": {"success": False}})
    out = json.loads(S.release_date("123"))
    assert out["reason"] == "steam-not-success"


def test_release_date_coming_soon(monkeypatch):
    monkeypatch.setattr(S, "_fetch", lambda a: {
        "9999": {"success": True, "data": {"release_date": {"coming_soon": True, "date": "Q4 2026"}}}
    })
    out = json.loads(S.release_date("9999"))
    assert out["comingSoon"] is True and out["releaseDate"] is None
    assert out["raw"] == "Q4 2026"


def test_release_date_happy(monkeypatch):
    monkeypatch.setattr(S, "_fetch", lambda a: {
        "220": {"success": True,
                "data": {"release_date": {"coming_soon": False, "date": "10 Aug, 2021"}}}
    })
    out = json.loads(S.release_date("220"))
    assert out["releaseDate"] == "2021-08-10"
    assert out["releaseYear"] == 2021
    assert out["comingSoon"] is False
    assert out["raw"] == "10 Aug, 2021"
