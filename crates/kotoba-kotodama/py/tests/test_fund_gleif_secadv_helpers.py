"""Tests for pure helpers in ingest/fund/gleif.py and ingest/fund/sec_adv.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.fund import gleif as GL
from kotodama.ingest.fund import sec_adv as SA


# ─── gleif: legal_entity_did_from_lei ────────────────────────────────────────

def test_lei_did_format() -> None:
    vid = GL.legal_entity_did_from_lei("abcdef1234567890xxxx")
    assert vid.startswith("at://did:web:legal-entity.etzhayyim.com/")
    assert "com.etzhayyim.apps.legalEntity.legalEntity" in vid


def test_lei_did_upcases_lei() -> None:
    vid = GL.legal_entity_did_from_lei("abcdef")
    # slug lowercases, but the upper() then slugged
    assert "abcdef" in vid


def test_lei_did_empty_returns_empty() -> None:
    assert GL.legal_entity_did_from_lei("") == ""
    assert GL.legal_entity_did_from_lei(None) == ""


def test_lei_did_deterministic() -> None:
    a = GL.legal_entity_did_from_lei("LEI0001234")
    b = GL.legal_entity_did_from_lei("LEI0001234")
    assert a == b


# ─── gleif: apply_gleif_enrichment ───────────────────────────────────────────

def test_apply_gleif_enrichment_adds_lei() -> None:
    entity = {"name": "Acme Corp", "confidence": 0.5}
    gleif = {"lei": "TESTLEI001"}
    result = GL.apply_gleif_enrichment(entity, gleif)
    assert "legal_entity_did" in result
    assert result["confidence"] >= 0.8


def test_apply_gleif_enrichment_no_lei_returns_copy() -> None:
    entity = {"name": "Test", "confidence": 0.5}
    gleif = {}
    result = GL.apply_gleif_enrichment(entity, gleif)
    assert result == dict(entity)


def test_apply_gleif_enrichment_adds_jurisdiction_if_missing() -> None:
    entity = {"name": "Foo"}
    gleif = {"lei": "L001", "jurisdiction": "JP"}
    result = GL.apply_gleif_enrichment(entity, gleif)
    assert result.get("jurisdiction") == "JP"


def test_apply_gleif_enrichment_does_not_overwrite_existing_jurisdiction() -> None:
    entity = {"name": "Foo", "jurisdiction": "US"}
    gleif = {"lei": "L001", "jurisdiction": "JP"}
    result = GL.apply_gleif_enrichment(entity, gleif)
    assert result["jurisdiction"] == "US"


def test_apply_gleif_enrichment_adds_domicile_from_country() -> None:
    entity = {"name": "Foo"}
    gleif = {"lei": "L001", "country": "DE"}
    result = GL.apply_gleif_enrichment(entity, gleif)
    assert result.get("domicile") == "DE"


def test_apply_gleif_enrichment_confidence_floor_at_08() -> None:
    entity = {"name": "Foo", "confidence": 0.1}
    gleif = {"lei": "L001"}
    result = GL.apply_gleif_enrichment(entity, gleif)
    assert result["confidence"] >= 0.8


def test_apply_gleif_enrichment_original_unchanged() -> None:
    entity = {"name": "Foo", "confidence": 0.9}
    gleif = {"lei": "L001", "jurisdiction": "US"}
    original_copy = dict(entity)
    GL.apply_gleif_enrichment(entity, gleif)
    assert entity == original_copy  # original not mutated


# ─── sec_adv: plan_sec_adv_shards ────────────────────────────────────────────

def test_plan_sec_adv_shards_default_count() -> None:
    result = SA.plan_sec_adv_shards()
    assert len(result) == 10


def test_plan_sec_adv_shards_custom_limit() -> None:
    result = SA.plan_sec_adv_shards(limit=5)
    assert len(result) == 5


def test_plan_sec_adv_shards_capped_at_50() -> None:
    result = SA.plan_sec_adv_shards(limit=200)
    assert len(result) <= 50


def test_plan_sec_adv_shards_min_is_1() -> None:
    result = SA.plan_sec_adv_shards(limit=0)
    assert len(result) >= 1


def test_plan_sec_adv_shards_have_source_id() -> None:
    result = SA.plan_sec_adv_shards(limit=3)
    for shard in result:
        assert shard.source_id
        assert shard.source_kind == "sec-form-adv"


def test_plan_sec_adv_shards_unique_shard_keys() -> None:
    result = SA.plan_sec_adv_shards(limit=5)
    keys = [s.shard_key for s in result]
    assert len(keys) == len(set(keys))


# ─── sec_adv: _first ─────────────────────────────────────────────────────────

def test_first_returns_first_non_empty() -> None:
    row = {"a": "", "b": "val", "c": "other"}
    assert SA._first(row, "a", "b", "c") == "val"


def test_first_all_empty_returns_empty() -> None:
    assert SA._first({"a": ""}, "a") == ""


def test_first_missing_key_returns_empty() -> None:
    assert SA._first({}, "missing") == ""


def test_first_whitespace_ignored() -> None:
    row = {"a": "  ", "b": "real value"}
    assert SA._first(row, "a", "b") == "real value"


# ─── sec_adv: _float_or_none ─────────────────────────────────────────────────

def test_float_or_none_valid() -> None:
    assert SA._float_or_none("1234.56") == 1234.56


def test_float_or_none_with_commas() -> None:
    assert SA._float_or_none("1,234,567") == 1234567.0


def test_float_or_none_empty_returns_none() -> None:
    assert SA._float_or_none("") is None
    assert SA._float_or_none(None) is None


def test_float_or_none_non_numeric_returns_none() -> None:
    assert SA._float_or_none("N/A") is None


def test_float_or_none_integer_string() -> None:
    assert SA._float_or_none("42") == 42.0


# ─── sec_adv: normalize_sec_adv_rows ─────────────────────────────────────────

def test_normalize_sec_adv_rows_basic() -> None:
    rows = [
        {
            "Primary Business Name": "Acme Capital",
            "CRD Number": "12345",
            "State": "NY",
        }
    ]
    managers, funds = SA.normalize_sec_adv_rows(rows)
    assert len(managers) == 1
    assert managers[0].manager_name == "Acme Capital"
    assert managers[0].regulator == "SEC"


def test_normalize_sec_adv_rows_skips_no_name() -> None:
    rows = [{"CRD Number": "123"}]
    managers, funds = SA.normalize_sec_adv_rows(rows)
    assert len(managers) == 0


def test_normalize_sec_adv_rows_extracts_fund() -> None:
    rows = [
        {
            "Primary Business Name": "Acme Capital",
            "Private Fund Name": "Acme Fund I",
            "Private Fund ID": "FUND001",
        }
    ]
    managers, funds = SA.normalize_sec_adv_rows(rows)
    assert len(funds) == 1
    assert funds[0].name == "Acme Fund I"


def test_normalize_sec_adv_rows_deduplicates_managers() -> None:
    rows = [
        {"Primary Business Name": "Same Firm", "CRD Number": "999", "Private Fund Name": "Fund A"},
        {"Primary Business Name": "Same Firm", "CRD Number": "999", "Private Fund Name": "Fund B"},
    ]
    managers, funds = SA.normalize_sec_adv_rows(rows)
    assert len(managers) == 1
    assert len(funds) == 2
