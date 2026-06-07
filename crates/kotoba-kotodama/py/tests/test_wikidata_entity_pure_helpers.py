"""Tests for pure helpers in handlers/wikidata_entity.py:
_claim_string_values, _best_publication_date."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_wikidata_entity"
if _MOD_NAME in sys.modules:
    WE = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if "wikidata" in k.lower()]:
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

    WE = _load_mod(_MOD_NAME, "kotodama/handlers/wikidata_entity.py")


def _make_claim(value: object, value_type: str = "string") -> dict:
    """Build a minimal Wikidata claim structure."""
    return {
        "mainsnak": {
            "datavalue": {
                "value": value,
                "type": value_type,
            }
        }
    }


def _make_entity(claims: dict) -> dict:
    return {"claims": claims}


# ─── _claim_string_values ────────────────────────────────────────────────────

def test_claim_string_values_simple_string() -> None:
    entity = _make_entity({"P5794": [_make_claim("12345")]})
    result = WE._claim_string_values(entity, "P5794")
    assert result == ["12345"]


def test_claim_string_values_entity_id_from_dict() -> None:
    entity = _make_entity({"P31": [_make_claim({"id": "Q5"}, "wikibase-entityid")]})
    result = WE._claim_string_values(entity, "P31")
    assert result == ["Q5"]


def test_claim_string_values_numeric_id_fallback() -> None:
    entity = _make_entity({"P31": [_make_claim({"numeric-id": 5}, "wikibase-entityid")]})
    result = WE._claim_string_values(entity, "P31")
    assert result == ["5"]


def test_claim_string_values_int_value() -> None:
    entity = _make_entity({"P1733": [_make_claim(99999)]})
    result = WE._claim_string_values(entity, "P1733")
    assert result == ["99999"]


def test_claim_string_values_deduplicates() -> None:
    entity = _make_entity({"P5794": [_make_claim("dup"), _make_claim("dup")]})
    result = WE._claim_string_values(entity, "P5794")
    assert result == ["dup"]


def test_claim_string_values_multiple_unique() -> None:
    entity = _make_entity({"P5794": [_make_claim("a"), _make_claim("b"), _make_claim("c")]})
    result = WE._claim_string_values(entity, "P5794")
    assert result == ["a", "b", "c"]


def test_claim_string_values_missing_prop_returns_empty() -> None:
    entity = _make_entity({})
    assert WE._claim_string_values(entity, "P9999") == []


def test_claim_string_values_no_claims_key() -> None:
    assert WE._claim_string_values({}, "P5794") == []


def test_claim_string_values_non_list_claims_returns_empty() -> None:
    entity = {"claims": {"P5794": "not-a-list"}}
    assert WE._claim_string_values(entity, "P5794") == []


def test_claim_string_values_skips_non_dict_claims() -> None:
    entity = _make_entity({"P5794": ["bad", _make_claim("good")]})
    result = WE._claim_string_values(entity, "P5794")
    assert result == ["good"]


def test_claim_string_values_skips_missing_datavalue() -> None:
    claim_no_dv = {"mainsnak": {}}
    entity = _make_entity({"P5794": [claim_no_dv, _make_claim("ok")]})
    result = WE._claim_string_values(entity, "P5794")
    assert result == ["ok"]


def test_claim_string_values_empty_string_value_excluded() -> None:
    entity = _make_entity({"P5794": [_make_claim("")]})
    result = WE._claim_string_values(entity, "P5794")
    assert result == []


# ─── _best_publication_date ──────────────────────────────────────────────────

def _make_time_claim(time_str: str) -> dict:
    return {
        "mainsnak": {
            "datavalue": {
                "value": {"time": time_str},
                "type": "time",
            }
        }
    }


def test_best_publication_date_simple() -> None:
    entity = _make_entity({"P577": [_make_time_claim("+2011-08-03T00:00:00Z")]})
    date, year = WE._best_publication_date(entity)
    assert date == "2011-08-03"
    assert year == 2011


def test_best_publication_date_picks_earliest() -> None:
    entity = _make_entity({"P577": [
        _make_time_claim("+2015-01-01T00:00:00Z"),
        _make_time_claim("+2010-06-15T00:00:00Z"),
        _make_time_claim("+2020-12-31T00:00:00Z"),
    ]})
    date, year = WE._best_publication_date(entity)
    assert date == "2010-06-15"
    assert year == 2010


def test_best_publication_date_no_p577_returns_none() -> None:
    entity = _make_entity({})
    assert WE._best_publication_date(entity) == (None, None)


def test_best_publication_date_no_claims_key() -> None:
    assert WE._best_publication_date({}) == (None, None)


def test_best_publication_date_non_list_returns_none() -> None:
    entity = {"claims": {"P577": "bad"}}
    assert WE._best_publication_date(entity) == (None, None)


def test_best_publication_date_skips_invalid_time() -> None:
    bad = {"mainsnak": {"datavalue": {"value": {"time": "not-a-date"}, "type": "time"}}}
    good = _make_time_claim("+2020-01-01T00:00:00Z")
    entity = _make_entity({"P577": [bad, good]})
    date, year = WE._best_publication_date(entity)
    assert date == "2020-01-01"


def test_best_publication_date_month_zero_clamped_to_1() -> None:
    entity = _make_entity({"P577": [_make_time_claim("+2005-00-00T00:00:00Z")]})
    date, year = WE._best_publication_date(entity)
    assert year == 2005


def test_best_publication_date_returns_iso_string() -> None:
    entity = _make_entity({"P577": [_make_time_claim("+1999-12-31T00:00:00Z")]})
    date, year = WE._best_publication_date(entity)
    assert date == "1999-12-31"
    assert year == 1999


def test_best_publication_date_without_plus_prefix() -> None:
    entity = _make_entity({"P577": [_make_time_claim("2018-03-15T00:00:00Z")]})
    date, year = WE._best_publication_date(entity)
    assert date == "2018-03-15"
    assert year == 2018
