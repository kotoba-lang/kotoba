"""Tests for pure helpers in handlers/contracts.py:
_normalize_name, _entity_hash, _mint_did, _rkey_for_org_did."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

_MOD_NAME = "_handler_contracts"
if _MOD_NAME in sys.modules:
    CO = sys.modules[_MOD_NAME]
else:
    try:
        from kotodama import registry as _reg
        for _k in [k for k in list(_reg._HANDLERS.keys()) if "contracts" in k.lower()]:
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

    CO = _load_mod(_MOD_NAME, "kotodama/handlers/contracts.py")


# ─── _normalize_name ─────────────────────────────────────────────────────────

def test_normalize_name_strips_inc() -> None:
    result = CO._normalize_name("Acme Inc.")
    assert "inc" not in result.lower()
    assert "acme" in result


def test_normalize_name_strips_ltd() -> None:
    assert "ltd" not in CO._normalize_name("Some Corp Ltd").lower()


def test_normalize_name_strips_llc() -> None:
    assert "llc" not in CO._normalize_name("Startup LLC").lower()


def test_normalize_name_strips_corp() -> None:
    assert "corp" not in CO._normalize_name("Global Corp").lower()


def test_normalize_name_strips_corporation() -> None:
    assert "corporation" not in CO._normalize_name("Giant Corporation").lower()


def test_normalize_name_strips_kk() -> None:
    assert "k.k." not in CO._normalize_name("日本技術 K.K.").lower()


def test_normalize_name_strips_kabushiki() -> None:
    result = CO._normalize_name("トヨタ自動車 株式会社")
    assert "株式会社" not in result


def test_normalize_name_lowercases() -> None:
    result = CO._normalize_name("TOYOTA MOTOR")
    assert result == result.lower()


def test_normalize_name_none_returns_empty() -> None:
    assert CO._normalize_name(None) == ""


def test_normalize_name_empty_returns_empty() -> None:
    assert CO._normalize_name("") == ""


def test_normalize_name_whitespace_collapsed() -> None:
    result = CO._normalize_name("Foo  Bar  Corp")
    assert "  " not in result


def test_normalize_name_no_leading_trailing_hyphens() -> None:
    result = CO._normalize_name("  Acme Corp  ")
    assert not result.startswith("-")
    assert not result.endswith("-")


def test_normalize_name_stable_for_same_input() -> None:
    assert CO._normalize_name("Sony Corp") == CO._normalize_name("Sony Corp")


# ─── _entity_hash ────────────────────────────────────────────────────────────

def test_entity_hash_returns_12_hex() -> None:
    result = CO._entity_hash("jpn", "123", "Acme", "2020-01-01")
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_entity_hash_deterministic() -> None:
    a = CO._entity_hash("jpn", "123", "Acme", "2020-01-01")
    b = CO._entity_hash("jpn", "123", "Acme", "2020-01-01")
    assert a == b


def test_entity_hash_different_countries_differ() -> None:
    a = CO._entity_hash("jpn", "123", "Acme", "2020-01-01")
    b = CO._entity_hash("usa", "123", "Acme", "2020-01-01")
    assert a != b


def test_entity_hash_different_ids_differ() -> None:
    a = CO._entity_hash("jpn", "001", "Acme", "2020-01-01")
    b = CO._entity_hash("jpn", "002", "Acme", "2020-01-01")
    assert a != b


def test_entity_hash_empty_parts_ok() -> None:
    result = CO._entity_hash("", "", "", "")
    assert len(result) == 12


# ─── _mint_did ───────────────────────────────────────────────────────────────

def test_mint_did_starts_with_sc_prefix() -> None:
    result = CO._mint_did("jpn", "001", "Test Corp", "2020-01-01")
    assert result.startswith(CO.SC_DID_PREFIX)


def test_mint_did_contains_country_alpha3() -> None:
    result = CO._mint_did("jpn", "001", "Test Corp", "2020-01-01")
    assert ":jpn:" in result


def test_mint_did_alpha3_truncated_to_3() -> None:
    result = CO._mint_did("japan", "001", "Test Corp", "2020-01-01")
    # Only first 3 chars used
    assert ":jap:" in result


def test_mint_did_empty_country_defaults_unk() -> None:
    result = CO._mint_did("", "001", "Corp", "2020-01-01")
    assert ":unk:" in result


def test_mint_did_deterministic() -> None:
    a = CO._mint_did("jpn", "001", "Test Corp", "2020-01-01")
    b = CO._mint_did("jpn", "001", "Test Corp", "2020-01-01")
    assert a == b


def test_mint_did_inc_stripped_before_hashing() -> None:
    # "Corp Inc" and "Corp Inc." should hash the same way
    a = CO._mint_did("usa", "001", "Acme Inc", "2020-01-01")
    b = CO._mint_did("usa", "001", "Acme Inc.", "2020-01-01")
    assert a == b


def test_mint_did_format_has_three_segments_after_prefix() -> None:
    result = CO._mint_did("jpn", "001", "Corp", "2020-01-01")
    # e.g. "did:web:social-contract.etzhayyim.com:entity:jpn:abc123..."
    parts = result.split(":")
    assert len(parts) >= 6


# ─── _rkey_for_org_did ───────────────────────────────────────────────────────

def test_rkey_for_org_did_returns_last_segment() -> None:
    did = "did:web:social-contract.etzhayyim.com:entity:jpn:abc123def456"
    result = CO._rkey_for_org_did(did)
    assert result == "abc123def456"


def test_rkey_for_org_did_unknown_on_empty() -> None:
    assert CO._rkey_for_org_did("") == "unknown"


def test_rkey_for_org_did_from_mint_did() -> None:
    did = CO._mint_did("jpn", "001", "Corp", "2020-01-01")
    rkey = CO._rkey_for_org_did(did)
    assert len(rkey) == 12


# ─── _row_to_resolve_dto ─────────────────────────────────────────────────────

def _make_resolve_row(**kwargs: object) -> dict:
    base: dict = {
        "did": "did:web:social-contract.etzhayyim.com:entity:jpn:abc123def456",
        "vertex_id": "at://did:web:x/com.etzhayyim.apps.contracts.organization/rkey1",
        "legal_entity_ref": "at://x/le/rkey2",
        "country": "JPN",
        "lei": "lei789",
        "national_id": "nat123",
        "name": "Acme Corp",
        "isic": "C10",
        "status": "active",
        "source": "gleif",
        "confidence": 0.9,
        "last_verified": "2024-01-01",
    }
    base.update(kwargs)
    return base


def test_row_to_resolve_dto_did_field() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row())
    assert dto["did"] == "did:web:social-contract.etzhayyim.com:entity:jpn:abc123def456"


def test_row_to_resolve_dto_vertex_id_mapped_to_camel() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row())
    assert dto["vertexId"] == "at://did:web:x/com.etzhayyim.apps.contracts.organization/rkey1"


def test_row_to_resolve_dto_legal_entity_ref_camel() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row())
    assert dto["legalEntityRef"] == "at://x/le/rkey2"


def test_row_to_resolve_dto_national_id_camel() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row())
    assert dto["nationalId"] == "nat123"


def test_row_to_resolve_dto_last_verified_camel() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row())
    assert dto["lastVerified"] == "2024-01-01"


def test_row_to_resolve_dto_country_preserved() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row())
    assert dto["country"] == "JPN"


def test_row_to_resolve_dto_confidence_preserved() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row())
    assert dto["confidence"] == 0.9


def test_row_to_resolve_dto_none_values_pass_through() -> None:
    dto = CO._row_to_resolve_dto(_make_resolve_row(lei=None, isic=None))
    assert dto["lei"] is None
    assert dto["isic"] is None


# ─── _row_to_projection ──────────────────────────────────────────────────────

def _make_le_row(**kwargs: object) -> dict:
    base: dict = {
        "vertex_id": "at://did:web:x/com.etzhayyim.apps.contracts.organization/rk1",
        "country": "JPN",
        "national_id": "12345",
        "name": "Acme Corp",
        "incorporated_date": "2010-01-01",
        "lei": "lei789",
        "legal_name": "Acme Corporation",
        "entity_type": "company",
        "isic": "C10",
        "duns": None,
        "wikidata_qid": None,
        "opencorporates_id": None,
        "status": "active",
        "source": "gleif",
        "source_record_id": "sr1",
        "last_verified": "2024-01-01",
    }
    base.update(kwargs)
    return base


def test_row_to_projection_has_did() -> None:
    result = CO._row_to_projection(_make_le_row())
    assert result["did"].startswith(CO.SC_DID_PREFIX)


def test_row_to_projection_did_contains_jpn() -> None:
    result = CO._row_to_projection(_make_le_row(country="JPN"))
    assert ":jpn:" in result["did"]


def test_row_to_projection_legal_entity_ref_from_vertex_id() -> None:
    result = CO._row_to_projection(_make_le_row())
    assert result["legal_entity_ref"] == "at://did:web:x/com.etzhayyim.apps.contracts.organization/rk1"


def test_row_to_projection_country_preserved() -> None:
    result = CO._row_to_projection(_make_le_row(country="USA"))
    assert result["country"] == "USA"


def test_row_to_projection_empty_country_gives_none() -> None:
    result = CO._row_to_projection(_make_le_row(country=""))
    assert result["country"] is None


def test_row_to_projection_name_preserved() -> None:
    result = CO._row_to_projection(_make_le_row(name="Sony Corp"))
    assert result["name"] == "Sony Corp"


def test_row_to_projection_lei_preserved() -> None:
    result = CO._row_to_projection(_make_le_row(lei="ABCDEF123456"))
    assert result["lei"] == "ABCDEF123456"


def test_row_to_projection_none_last_verified_gives_none() -> None:
    result = CO._row_to_projection(_make_le_row(last_verified=None))
    assert result["last_verified"] is None


def test_row_to_projection_returns_dict() -> None:
    result = CO._row_to_projection(_make_le_row())
    assert isinstance(result, dict)


def test_row_to_projection_has_did_key() -> None:
    result = CO._row_to_projection(_make_le_row())
    assert "did" in result


def test_row_to_projection_deterministic() -> None:
    row = _make_le_row()
    a = CO._row_to_projection(row)
    b = CO._row_to_projection(row)
    assert a["did"] == b["did"]
