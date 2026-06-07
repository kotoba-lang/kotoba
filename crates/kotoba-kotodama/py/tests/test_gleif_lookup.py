"""
Unit tests for kotodama.handlers.gleif_lookup.

Pure-function coverage (no live network):
- `_url_for` encodes spaces + ampersands correctly.
- `_flatten_hit` pulls out id / legalName / country / jurisdiction +
  trims a 10-char incorporationDate out of the full ISO stamp.
- `_addr_line` joins addressLines + city + region + postal + country.
- `_pick_best` honours country hint, falls back to first hit, returns {}
  on empty input.
- `lookup` short-circuits on empty name + envelopes transport failures.

Live-network `lookup('Alibaba Cloud US LLC', 'US')` sanity is left to
the integration suite so this file stays offline-safe.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
import types
from pathlib import Path as _P


# Stub arrow_udf so the @udf decorator is a no-op when the module loads
# outside the production container.
if "arrow_udf" not in sys.modules:
    stub = types.ModuleType("arrow_udf")

    def _udf(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap

    stub.udf = _udf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = stub


_src = _P(__file__).resolve().parents[1] / "src/kotodama/handlers/gleif_lookup.py"
_spec = _ilu.spec_from_file_location("_gleif_under_test", _src)
G = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(G)  # type: ignore[union-attr]


# ─── _url_for ───────────────────────────────────────────────────────────


def test_url_for_encodes_spaces():
    url = G._url_for("Alibaba Cloud US LLC")
    assert "filter%5Bentity.legalName%5D=Alibaba+Cloud+US+LLC" in url \
        or "filter%5Bentity.legalName%5D=Alibaba%20Cloud%20US%20LLC" in url
    assert "page%5Bsize%5D=5" in url


def test_url_for_encodes_ampersand():
    url = G._url_for("A & B")
    assert "%26" in url  # '&' must be percent-encoded in the value


# ─── _flatten_hit ───────────────────────────────────────────────────────


_SAMPLE_HIT = {
    "id": "9845000B4FL02B89BB41",
    "attributes": {
        "entity": {
            "legalName": {"name": "ALIBABA CLOUD US LLC"},
            "legalAddress": {
                "country": "US",
                "city": "Los Angeles",
                "region": "US-DE",
                "postalCode": "90071",
                "addressLines": ["500 S Grand Ave"],
            },
            "jurisdiction": "US-DE",
            "registeredAs": "6234567",
            "status": "ACTIVE",
            "creationDate": "2019-11-04T00:00:00.000Z",
        },
    },
}


def test_flatten_hit_core_fields():
    out = G._flatten_hit(_SAMPLE_HIT)
    assert out["lei"] == "9845000B4FL02B89BB41"
    assert out["legalName"] == "ALIBABA CLOUD US LLC"
    assert out["country"] == "US"
    assert out["jurisdiction"] == "US-DE"
    assert out["registrationNumber"] == "6234567"
    assert out["status"] == "ACTIVE"


def test_flatten_hit_trims_creation_date():
    out = G._flatten_hit(_SAMPLE_HIT)
    assert out["incorporationDate"] == "2019-11-04"


def test_flatten_hit_address_joined():
    out = G._flatten_hit(_SAMPLE_HIT)
    assert out["address"] == "500 S Grand Ave, Los Angeles, US-DE, 90071, US"


def test_flatten_hit_malformed():
    assert G._flatten_hit("not a dict") == {}  # type: ignore[arg-type]
    assert G._flatten_hit({}) == {"lei": None, "legalName": None, "country": None,
                                  "jurisdiction": None, "registrationNumber": None,
                                  "status": None, "incorporationDate": None,
                                  "address": ""}


# ─── _addr_line ─────────────────────────────────────────────────────────


def test_addr_line_handles_missing_fields():
    addr = {"city": "Tokyo", "country": "JP"}
    assert G._addr_line(addr) == "Tokyo, JP"


def test_addr_line_skips_empty_values():
    addr = {"city": "", "country": "JP"}
    assert G._addr_line(addr) == "JP"


def test_addr_line_none_returns_empty():
    assert G._addr_line(None) == ""


# ─── _pick_best ─────────────────────────────────────────────────────────


def test_pick_best_empty():
    assert G._pick_best([], "US") == {}


def test_pick_best_country_hint_matches():
    hits = [
        {"id": "CN", "attributes": {"entity": {"legalAddress": {"country": "CN"}}}},
        {"id": "US", "attributes": {"entity": {"legalAddress": {"country": "US"}}}},
    ]
    assert G._pick_best(hits, "US")["lei"] == "US"


def test_pick_best_no_match_falls_back_to_first():
    hits = [
        {"id": "CN", "attributes": {"entity": {"legalAddress": {"country": "CN"}}}},
        {"id": "JP", "attributes": {"entity": {"legalAddress": {"country": "JP"}}}},
    ]
    assert G._pick_best(hits, "US")["lei"] == "CN"


def test_pick_best_no_hint_returns_first():
    hits = [
        {"id": "CN", "attributes": {"entity": {"legalAddress": {"country": "CN"}}}},
        {"id": "US", "attributes": {"entity": {"legalAddress": {"country": "US"}}}},
    ]
    assert G._pick_best(hits, "")["lei"] == "CN"


# ─── lookup early-return / monkeypatched transport ──────────────────────


def test_lookup_empty_name(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("should not fetch")
    monkeypatch.setattr(G, "_gleif_fetch", _boom)
    out = json.loads(G.lookup("", "US"))
    assert out == {"lei": None, "error": "name required"}


def test_lookup_zero_hits(monkeypatch):
    monkeypatch.setattr(G, "_gleif_fetch", lambda name: [])
    out = json.loads(G.lookup("Nonexistent Co", "XX"))
    assert out == {"lei": None, "name": "Nonexistent Co", "hitCount": 0}


def test_lookup_happy(monkeypatch):
    monkeypatch.setattr(G, "_gleif_fetch", lambda name: [_SAMPLE_HIT])
    out = json.loads(G.lookup("Alibaba Cloud US LLC", "US"))
    assert out["lei"] == "9845000B4FL02B89BB41"
    assert out["hitCount"] == 1
    assert out["name"] == "Alibaba Cloud US LLC"
    assert out["country"] == "US"


def test_lookup_country_hint_filters(monkeypatch):
    cn_hit = {
        "id": "CHINA-LEI-12345678901234",
        "attributes": {"entity": {"legalAddress": {"country": "CN"},
                                  "legalName": {"name": "CN CO"}}},
    }
    monkeypatch.setattr(G, "_gleif_fetch", lambda name: [cn_hit, _SAMPLE_HIT])
    out_us = json.loads(G.lookup("Alibaba", "US"))
    assert out_us["country"] == "US"
    out_cn = json.loads(G.lookup("Alibaba", "CN"))
    assert out_cn["country"] == "CN"
