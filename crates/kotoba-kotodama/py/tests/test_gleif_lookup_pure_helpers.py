"""Tests for pure helpers in handlers/gleif_lookup.py:
_url_for, _addr_line, _flatten_hit, _pick_best."""

from __future__ import annotations

import sys
import types
import importlib.util
import urllib.parse
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_gleif_lookup"
if _MOD_NAME in sys.modules:
    GL = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if "gleif" in k.lower() and "lookup" in k.lower()]:
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

    GL = _load_mod(_MOD_NAME, "kotodama/handlers/gleif_lookup.py")


# ─── _url_for ────────────────────────────────────────────────────────────────

def test_url_for_starts_with_gleif_base() -> None:
    result = GL._url_for("Acme Corp")
    assert result.startswith(GL._GLEIF_URL)


def test_url_for_contains_encoded_name() -> None:
    result = GL._url_for("Tokyo Electronics")
    parsed = urllib.parse.urlparse(result)
    qs = urllib.parse.parse_qs(parsed.query)
    assert "filter[entity.legalName]" in qs
    assert qs["filter[entity.legalName]"][0] == "Tokyo Electronics"


def test_url_for_encodes_spaces() -> None:
    result = GL._url_for("Acme Corp Ltd")
    assert " " not in result


def test_url_for_contains_page_size() -> None:
    result = GL._url_for("Test Co")
    assert "page%5Bsize%5D" in result or "page[size]" in result


def test_url_for_empty_name_ok() -> None:
    result = GL._url_for("")
    assert GL._GLEIF_URL in result


# ─── _addr_line ──────────────────────────────────────────────────────────────

def test_addr_line_full_address() -> None:
    addr = {
        "addressLines": ["1-1-1 Chiyoda"],
        "city": "Tokyo",
        "region": "Tokyo-to",
        "postalCode": "100-0001",
        "country": "JP",
    }
    result = GL._addr_line(addr)
    assert "Tokyo" in result
    assert "JP" in result


def test_addr_line_none_returns_empty() -> None:
    assert GL._addr_line(None) == ""


def test_addr_line_non_dict_returns_empty() -> None:
    assert GL._addr_line("not a dict") == ""  # type: ignore[arg-type]


def test_addr_line_empty_dict_returns_empty() -> None:
    assert GL._addr_line({}) == ""


def test_addr_line_only_country() -> None:
    result = GL._addr_line({"country": "US"})
    assert "US" in result


def test_addr_line_skips_empty_strings() -> None:
    addr = {"city": "", "country": "JP"}
    result = GL._addr_line(addr)
    assert result == "JP"


def test_addr_line_address_lines_list() -> None:
    addr = {"addressLines": ["Line1", "Line2"], "country": "DE"}
    result = GL._addr_line(addr)
    assert "Line1" in result
    assert "Line2" in result


# ─── _flatten_hit ────────────────────────────────────────────────────────────

def _make_hit(lei: str = "ABC123", name: str = "Test Corp", country: str = "JP") -> dict:
    return {
        "id": lei,
        "attributes": {
            "entity": {
                "legalName": {"name": name},
                "legalAddress": {"country": country, "city": "Tokyo"},
                "status": "ACTIVE",
                "jurisdiction": "JP",
                "registeredAs": "0000-00-000000",
                "creationDate": "2010-04-01T00:00:00Z",
            }
        }
    }


def test_flatten_hit_extracts_lei() -> None:
    result = GL._flatten_hit(_make_hit("LEI001"))
    assert result["lei"] == "LEI001"


def test_flatten_hit_extracts_legal_name() -> None:
    result = GL._flatten_hit(_make_hit(name="Sony Corp"))
    assert result["legalName"] == "Sony Corp"


def test_flatten_hit_extracts_country() -> None:
    result = GL._flatten_hit(_make_hit(country="US"))
    assert result["country"] == "US"


def test_flatten_hit_extracts_status() -> None:
    result = GL._flatten_hit(_make_hit())
    assert result["status"] == "ACTIVE"


def test_flatten_hit_incorporation_date_trimmed() -> None:
    result = GL._flatten_hit(_make_hit())
    assert result["incorporationDate"] == "2010-04-01"


def test_flatten_hit_non_dict_returns_empty() -> None:
    assert GL._flatten_hit("bad") == {}  # type: ignore[arg-type]


def test_flatten_hit_missing_attributes_graceful() -> None:
    result = GL._flatten_hit({"id": "L001"})
    assert result["lei"] == "L001"
    assert result["legalName"] is None


def test_flatten_hit_has_all_keys() -> None:
    result = GL._flatten_hit(_make_hit())
    for key in ("lei", "legalName", "country", "jurisdiction", "registrationNumber", "status", "incorporationDate", "address"):
        assert key in result


# ─── _pick_best ──────────────────────────────────────────────────────────────

def test_pick_best_empty_hits_returns_empty() -> None:
    assert GL._pick_best([], "JP") == {}


def test_pick_best_prefers_country_hint() -> None:
    hits = [_make_hit("L1", "Corp A", "US"), _make_hit("L2", "Corp B", "JP")]
    result = GL._pick_best(hits, "JP")
    assert result["lei"] == "L2"


def test_pick_best_first_when_no_hint() -> None:
    hits = [_make_hit("L1", "Corp A", "US"), _make_hit("L2", "Corp B", "JP")]
    result = GL._pick_best(hits, "")
    assert result["lei"] == "L1"


def test_pick_best_first_when_hint_not_matched() -> None:
    hits = [_make_hit("L1", "Corp A", "US"), _make_hit("L2", "Corp B", "US")]
    result = GL._pick_best(hits, "JP")
    assert result["lei"] == "L1"


def test_pick_best_hint_case_insensitive() -> None:
    hits = [_make_hit("L1", "Corp A", "US"), _make_hit("L2", "Corp B", "JP")]
    result = GL._pick_best(hits, "jp")
    assert result["lei"] == "L2"


def test_pick_best_single_hit_no_hint() -> None:
    hits = [_make_hit("L1", "Only Corp", "US")]
    result = GL._pick_best(hits, "")
    assert result["lei"] == "L1"
