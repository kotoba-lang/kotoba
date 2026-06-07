"""
Unit tests for kotodama.handlers.contracts (ADR-0049 contracts pilot).

Pure-function coverage:
- Name normalization strips legal suffixes and folds whitespace.
- Entity hash is deterministic (same input → same 12 hex chars).
- DID format matches `did:web:social-contract.etzhayyim.com:entity:{alpha3}:{hash}`.
- _rkey_for_org_did extracts the hash suffix.

Handler coverage (async):
- mintOrganizationDid rejects missing input.
- mintOrganizationDid returns {ok, did, inserted} for a known row.
- projectFromLegalEntity returns {ok, scanned, inserted, skipped, dids}.
- resolveOrganization rejects missing filters.

DB interactions are tested against a minimal in-memory pool stub that
records `.fetchrow` / `.fetch` / `.fetchval` calls. No live RisingWave
required.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path as _P
from typing import Any

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf() registers cleanly without the runtime dep.
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub

# Load contracts.py directly — bypasses handlers/__init__.py which
# eagerly imports shinka (needs langgraph) and other handlers.
_src = _P(__file__).resolve().parents[1] / "src/kotodama/handlers/contracts.py"
_spec = importlib.util.spec_from_file_location("_contracts_under_test", _src)
C = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(C)  # type: ignore[union-attr]

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_normalize_name_strips_suffixes_and_whitespace():
    assert C._normalize_name("Apple Inc.") == "apple"
    assert C._normalize_name("Acme Corp") == "acme"
    assert C._normalize_name("  Foo   Bar   LLC  ") == "foo-bar"
    assert C._normalize_name("株式会社トヨタ 株式会社") == "株式会社トヨタ"
    assert C._normalize_name(None) == ""
    assert C._normalize_name("") == ""


def test_entity_hash_is_deterministic():
    a = C._entity_hash("jpn", "1234567890123", "toyota", "1937-08-28")
    b = C._entity_hash("jpn", "1234567890123", "toyota", "1937-08-28")
    assert a == b
    assert len(a) == 12
    assert all(ch in "0123456789abcdef" for ch in a)


def test_entity_hash_varies_with_input():
    base = C._entity_hash("jpn", "1234567890123", "toyota", "1937-08-28")
    assert C._entity_hash("usa", "1234567890123", "toyota", "1937-08-28") != base
    assert C._entity_hash("jpn", "9999999999999", "toyota", "1937-08-28") != base
    assert C._entity_hash("jpn", "1234567890123", "honda", "1937-08-28") != base


def test_mint_did_shape():
    did = C._mint_did("JPN", "1234567890123", "Toyota Motor Corp", "1937-08-28")
    assert did.startswith("did:web:social-contract.etzhayyim.com:entity:jpn:")
    parts = did.rsplit(":", 1)
    assert len(parts[-1]) == 12


def test_mint_did_fallback_when_country_empty():
    did = C._mint_did("", "x", "Acme", "2020-01-01")
    assert did.startswith("did:web:social-contract.etzhayyim.com:entity:unk:")


def test_rkey_for_org_did_extracts_hash():
    did = "did:web:social-contract.etzhayyim.com:entity:jpn:abcdef012345"
    assert C._rkey_for_org_did(did) == "abcdef012345"


def test_row_to_projection_maps_fields():
    src = {
        "vertex_id": "at://le/vid1",
        "country": "jpn",
        "lei": "LEI123",
        "national_id": "1234567890123",
        "name": "Toyota Motor Corp",
        "legal_name": "トヨタ自動車株式会社",
        "entity_type": "kk",
        "isic": "2910",
        "duns": None,
        "wikidata_qid": "Q53268",
        "opencorporates_id": "jp/123",
        "status": "active",
        "source": "nta",
        "source_record_id": "nta-1234567890123",
        "last_verified": "2026-04-22T00:00:00Z",
        "incorporated_date": "1937-08-28",
    }
    out = C._row_to_projection(src)
    assert out["legal_entity_ref"] == "at://le/vid1"
    assert out["country"] == "jpn"
    assert out["lei"] == "LEI123"
    assert out["did"].startswith("did:web:social-contract.etzhayyim.com:entity:jpn:")


# ---------------------------------------------------------------------------
# In-memory pool stub
# ---------------------------------------------------------------------------


class _StubPool:
    """
    Minimal asyncpg-compatible pool stub. Records calls + lets the test
    pre-load rows keyed by (query signature, *args).

    `fetchrow` returns the first dict in `rows_by_query[query_key]`.
    `fetch` returns the full list.
    `fetchval` returns `inserted_vertex_ids.pop()` when the query is an
    INSERT ... RETURNING, else None.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.rows: dict[str, list[dict[str, Any]]] = {}
        self.insert_returns: list[str | None] = []

    def _key(self, query: str) -> str:
        return query.strip().splitlines()[0].strip()

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.calls.append((self._key(query), args))
        rows = self.rows.get(self._key(query), [])
        return rows[0] if rows else None

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((self._key(query), args))
        return list(self.rows.get(self._key(query), []))

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.calls.append((self._key(query), args))
        if self.insert_returns:
            return self.insert_returns.pop(0)
        return None

    async def execute(self, query: str, *args: Any) -> None:
        self.calls.append((self._key(query), args))


@pytest.fixture
def stub_pool(monkeypatch: pytest.MonkeyPatch) -> _StubPool:
    pool = _StubPool()
    # Context.__init__ does self.db = _UnwiredDb(). Replace the factory
    # so ctx.db == pool inside each handler call.
    import kotodama.context as _ctx_mod
    monkeypatch.setattr(_ctx_mod, "_UnwiredDb", lambda: pool)
    return pool


# ---------------------------------------------------------------------------
# mintOrganizationDid
# ---------------------------------------------------------------------------


def test_mintOrganizationDid_requires_vertex_id():
    import asyncio
    out = json.loads(asyncio.run(C.mint_organization_did.__wrapped__("{}")))  # type: ignore[attr-defined]
    assert "error" in out


def test_mintOrganizationDid_rejects_invalid_json():
    import asyncio
    out = json.loads(asyncio.run(C.mint_organization_did.__wrapped__("not-json")))  # type: ignore[attr-defined]
    assert "error" in out


def test_mintOrganizationDid_projects_row(stub_pool: _StubPool):
    import asyncio
    # Pre-load legal_entity row for the fetchrow query (first line as key).
    stub_pool.rows["SELECT vertex_id, country, lei, national_id, name, legal_name, entity_type, isic,"] = [
        {
            "vertex_id": "at://did:web:legal-entity.etzhayyim.com/com.etzhayyim.apps.legalEntity.legalEntity/r1",
            "country": "jpn",
            "lei": "LEI-ABC",
            "national_id": "1234567890123",
            "name": "Toyota Motor Corp",
            "legal_name": "トヨタ自動車株式会社",
            "entity_type": "kk",
            "isic": "2910",
            "duns": None,
            "wikidata_qid": "Q53268",
            "opencorporates_id": "jp/123",
            "status": "active",
            "source": "nta",
            "source_record_id": "nta-1234567890123",
            "last_verified": "2026-04-22T00:00:00Z",
            "incorporated_date": "1937-08-28",
        }
    ]
    # Simulate "row inserted" by the INSERT ... RETURNING.
    stub_pool.insert_returns.append("at://did:web:social-contract.etzhayyim.com:entity:jpn:xxx/...")

    body = json.dumps({"legalEntityVertexId": "at://did:web:legal-entity.etzhayyim.com/com.etzhayyim.apps.legalEntity.legalEntity/r1"})
    out = json.loads(asyncio.run(C.mint_organization_did.__wrapped__(body)))  # type: ignore[attr-defined]
    assert out["ok"] is True
    assert out["did"].startswith("did:web:social-contract.etzhayyim.com:entity:jpn:")
    assert out["inserted"] is True


# ---------------------------------------------------------------------------
# projectFromLegalEntity
# ---------------------------------------------------------------------------


def test_projectFromLegalEntity_single_by_lei(stub_pool: _StubPool):
    import asyncio
    # Any match on the LEI lookup branch.
    stub_pool.rows["SELECT vertex_id, country, lei, national_id, name, legal_name, entity_type, isic,"] = [
        {
            "vertex_id": "at://le/vid-by-lei",
            "country": "usa",
            "lei": "LEI-USA-001",
            "national_id": "DE-123",
            "name": "Acme LLC",
            "legal_name": "Acme LLC",
            "entity_type": "llc",
            "isic": None,
            "duns": None,
            "wikidata_qid": None,
            "opencorporates_id": None,
            "status": "active",
            "source": "gleif",
            "source_record_id": "LEI-USA-001",
            "last_verified": "2026-04-22T00:00:00Z",
            "incorporated_date": "2000-01-01",
        }
    ]
    stub_pool.insert_returns.append("at://new-row/abc")

    out = json.loads(asyncio.run(C.project_from_legal_entity.__wrapped__(json.dumps({"lei": "LEI-USA-001"}))))  # type: ignore[attr-defined]
    assert out["ok"] is True
    assert out["scanned"] == 1
    assert out["inserted"] == 1
    assert len(out["dids"]) == 1
    assert out["dids"][0].startswith("did:web:social-contract.etzhayyim.com:entity:usa:")


def test_projectFromLegalEntity_rejects_missing_lei_row(stub_pool: _StubPool):
    import asyncio
    # No rows preloaded → fetchrow returns None.
    out = json.loads(asyncio.run(C.project_from_legal_entity.__wrapped__(json.dumps({"lei": "missing"}))))  # type: ignore[attr-defined]
    assert "error" in out


def test_projectFromLegalEntity_backfill_respects_limit(stub_pool: _StubPool):
    import asyncio
    # Two rows queued for backfill; both insert OK.
    stub_pool.rows["SELECT le.vertex_id, le.country, le.lei, le.national_id, le.name, le.legal_name,"] = [
        {
            "vertex_id": f"at://le/b{i}",
            "country": "jpn",
            "lei": None,
            "national_id": f"{i:013d}",
            "name": f"Co{i}",
            "legal_name": None,
            "entity_type": None,
            "isic": None,
            "duns": None,
            "wikidata_qid": None,
            "opencorporates_id": None,
            "status": None,
            "source": "nta",
            "source_record_id": f"nta-{i}",
            "last_verified": None,
            "incorporated_date": None,
        }
        for i in range(2)
    ]
    stub_pool.insert_returns.extend(["vid1", "vid2"])
    out = json.loads(asyncio.run(C.project_from_legal_entity.__wrapped__(json.dumps({"batchLimit": 2}))))  # type: ignore[attr-defined]
    assert out["scanned"] == 2
    assert out["inserted"] == 2
    assert out["skipped"] == 0


# ---------------------------------------------------------------------------
# resolveOrganization
# ---------------------------------------------------------------------------


def test_resolveOrganization_requires_a_filter(stub_pool: _StubPool):
    import asyncio
    out = json.loads(asyncio.run(C.resolve_organization.__wrapped__("{}")))  # type: ignore[attr-defined]
    assert "error" in out


def test_resolveOrganization_by_did(stub_pool: _StubPool):
    import asyncio
    did = "did:web:social-contract.etzhayyim.com:entity:jpn:abcdef012345"
    stub_pool.rows["SELECT vertex_id, did, legal_entity_ref, country, lei, national_id, name,"] = [
        {
            "vertex_id": f"at://{did}/com.etzhayyim.apps.contracts.organization/abcdef012345",
            "did": did,
            "legal_entity_ref": "at://le/src",
            "country": "jpn",
            "lei": "LEI",
            "national_id": "1234567890123",
            "name": "Toyota",
            "isic": "2910",
            "status": "active",
            "source": "nta",
            "confidence": 1.0,
            "last_verified": "2026-04-22T00:00:00Z",
        }
    ]
    out = json.loads(asyncio.run(C.resolve_organization.__wrapped__(json.dumps({"did": did}))))  # type: ignore[attr-defined]
    assert out["total"] == 1
    assert out["organizations"][0]["did"] == did
