"""
Unit tests for kotodama.handlers.wikidata_entity.

Pure-function coverage (no live network):
- `_claim_string_values` pulls string / entity-id / numeric-id scalars,
  dedups in order, ignores dict values without `id`/`numeric-id`.
- `_best_publication_date` returns the earliest parseable P577 as ISO +
  year, falling back to (None, None) for zero-date claims.
- `entity_claims` rejects malformed qids + envelopes fetch failures.

Live `entity_claims('Q10757')` is reserved for the integration suite.
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


_src = _P(__file__).resolve().parents[1] / "src/kotodama/handlers/wikidata_entity.py"
_spec = _ilu.spec_from_file_location("_wikidata_under_test", _src)
W = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(W)  # type: ignore[union-attr]


# Build a minimal entity dict by hand — wbgetentities responses are too
# large to inline and drift over time, so fixtures stay synthetic.

def _snak(value):
    return {"mainsnak": {"datavalue": {"value": value}}}


def _ent(claims_map):
    return {"claims": claims_map}


# ─── _claim_string_values ───────────────────────────────────────────────


def test_claim_values_strings():
    ent = _ent({"P1733": [_snak("123"), _snak("456")]})
    assert W._claim_string_values(ent, "P1733") == ["123", "456"]


def test_claim_values_dedups_preserving_order():
    ent = _ent({"P1733": [_snak("123"), _snak("456"), _snak("123")]})
    assert W._claim_string_values(ent, "P1733") == ["123", "456"]


def test_claim_values_entity_id():
    ent = _ent({"P31": [_snak({"id": "Q100", "numeric-id": 100})]})
    assert W._claim_string_values(ent, "P31") == ["Q100"]


def test_claim_values_numeric_id_fallback():
    # No 'id' key — fall back to numeric-id as string
    ent = _ent({"P31": [_snak({"numeric-id": 42})]})
    assert W._claim_string_values(ent, "P31") == ["42"]


def test_claim_values_numeric_scalar():
    ent = _ent({"P2047": [_snak(3.14)]})
    assert W._claim_string_values(ent, "P2047") == ["3.14"]


def test_claim_values_unknown_property():
    assert W._claim_string_values(_ent({}), "P999") == []


def test_claim_values_not_a_list():
    assert W._claim_string_values(_ent({"P1": "oops"}), "P1") == []


def test_claim_values_malformed_snak():
    ent = {"claims": {"P1": [{"no_mainsnak": True}, {"mainsnak": "not a dict"}]}}
    assert W._claim_string_values(ent, "P1") == []


# ─── _best_publication_date ─────────────────────────────────────────────


def _time_snak(iso_prefix: str):
    # Wikidata time value shape
    return {"mainsnak": {"datavalue": {"value": {"time": iso_prefix, "precision": 11}}}}


def test_best_p577_single_date():
    ent = _ent({"P577": [_time_snak("+2021-08-10T00:00:00Z")]})
    iso, year = W._best_publication_date(ent)
    assert iso == "2021-08-10" and year == 2021


def test_best_p577_picks_earliest():
    ent = _ent({"P577": [
        _time_snak("+2023-01-15T00:00:00Z"),
        _time_snak("+2021-08-10T00:00:00Z"),
        _time_snak("+2022-05-01T00:00:00Z"),
    ]})
    iso, year = W._best_publication_date(ent)
    assert iso == "2021-08-10" and year == 2021


def test_best_p577_clamps_month_day_zero():
    # Wikidata sometimes encodes year-only as 2021-00-00; we clamp to 1.
    ent = _ent({"P577": [_time_snak("+2021-00-00T00:00:00Z")]})
    iso, year = W._best_publication_date(ent)
    assert iso == "2021-01-01" and year == 2021


def test_best_p577_missing():
    assert W._best_publication_date(_ent({})) == (None, None)


def test_best_p577_malformed():
    ent = _ent({"P577": [_time_snak("garbage")]})
    assert W._best_publication_date(ent) == (None, None)


# ─── entity_claims early-return + transport ─────────────────────────────


def test_entity_claims_invalid_qid(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("should not fetch for invalid qid")
    monkeypatch.setattr(W, "_fetch_entity", _boom)
    out = json.loads(W.entity_claims("not-a-qid"))
    assert out["error"] == "invalid qid"
    assert out["igdbIds"] == [] and out["steamAppIds"] == [] and out["publicationDate"] is None


def test_entity_claims_empty_qid(monkeypatch):
    monkeypatch.setattr(W, "_fetch_entity", lambda q: None)
    out = json.loads(W.entity_claims(""))
    assert out["error"] == "invalid qid"


def test_entity_claims_fetch_failure(monkeypatch):
    monkeypatch.setattr(W, "_fetch_entity", lambda q: None)
    out = json.loads(W.entity_claims("Q1"))
    assert out == {
        "qid": "Q1", "error": "fetch failed",
        "igdbIds": [], "steamAppIds": [], "officialUrls": [],
        "publicationDate": None, "publicationYear": None,
    }


def test_entity_claims_happy(monkeypatch):
    ent = _ent({
        "P5794": [_snak("42")],
        "P1733": [_snak("220")],
        "P856": [_snak("https://example.com")],
        "P577": [_time_snak("+2011-08-03T00:00:00Z")],
    })
    monkeypatch.setattr(W, "_fetch_entity", lambda q: ent)
    out = json.loads(W.entity_claims("Q10757"))
    assert out["qid"] == "Q10757"
    assert out["igdbIds"] == ["42"]
    assert out["steamAppIds"] == ["220"]
    assert out["officialUrls"] == ["https://example.com"]
    assert out["publicationDate"] == "2011-08-03"
    assert out["publicationYear"] == 2011
    assert out["error"] is None
