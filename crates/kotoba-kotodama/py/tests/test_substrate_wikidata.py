"""Tests for kotodama.substrate.wikidata — Wikidata SPARQL → ownership.

Mirror of TS 60-apps/.../wikidata-ingest.test.ts. Mocks the Etzhayyim
client via the same httpx MockTransport pattern used in test_substrate.py.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from kotodama.substrate import Etzhayyim
from kotodama.substrate.wikidata import (
    BulkOwnershipStats,
    KNOWN_RELATIONS,
    OWNERSHIP_COLLECTION,
    WIKIDATA_SOURCE_DID,
    OwnershipConverterOptions,
    ingest_ownership_from_wikidata,
    qid_from_entity_uri,
    wikidata_row_to_ownership,
)


PDS_FIX = "https://pds.test.local"


def _client(handler) -> Etzhayyim:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(base_url=PDS_FIX, transport=transport)
    return Etzhayyim(
        did="did:web:maps.etzhayyim.com",
        pds_url=PDS_FIX,
        session_jwt="test-jwt",
        http_client=http,
    )


# ─── fixtures ────────────────────────────────────────────────────────


def owner_binding(
    imo: str,
    owner_qid: str,
    owner_label: str,
    owner_lei: str | None = None,
    country: str | None = None,
) -> dict:
    b: dict[str, dict] = {
        "imo": {"type": "literal", "value": imo},
        "owner": {"type": "uri", "value": f"http://www.wikidata.org/entity/{owner_qid}"},
        "ownerLabel": {"type": "literal", "value": owner_label},
    }
    if owner_lei:
        b["ownerLEI"] = {"type": "literal", "value": owner_lei}
    if country:
        b["ownerCountryCode"] = {"type": "literal", "value": country}
    return b


def operator_binding(
    imo: str,
    op_qid: str,
    op_label: str,
    op_lei: str | None = None,
) -> dict:
    b: dict[str, dict] = {
        "imo": {"type": "literal", "value": imo},
        "operator": {"type": "uri", "value": f"http://www.wikidata.org/entity/{op_qid}"},
        "operatorLabel": {"type": "literal", "value": op_label},
    }
    if op_lei:
        b["operatorLEI"] = {"type": "literal", "value": op_lei}
    return b


# ─── pure helpers ────────────────────────────────────────────────────


def test_qid_from_entity_uri():
    assert qid_from_entity_uri("http://www.wikidata.org/entity/Q486156") == "Q486156"
    assert qid_from_entity_uri("https://www.wikidata.org/entity/Q1") == "Q1"
    assert qid_from_entity_uri("not a uri") is None
    assert qid_from_entity_uri(None) is None
    # Lexemes / properties / etc. are not Q-items.
    assert qid_from_entity_uri("http://www.wikidata.org/entity/L42") is None


def test_known_relations_includes_operates_manages():
    assert "OwnsProperty" in KNOWN_RELATIONS
    assert "Operates" in KNOWN_RELATIONS
    assert "Manages" in KNOWN_RELATIONS
    assert len(KNOWN_RELATIONS) == 7


# ─── converter (pure) ───────────────────────────────────────────────


def test_owner_binding_with_lei_produces_OwnsProperty_record():
    conv = wikidata_row_to_ownership(
        owner_binding("9074729", "Q486156", "Toyota Tsusho", "353800ZNORS39N56Y897", "JP"),
        entity_lei_key="ownerLEI",
        entity_label_key="ownerLabel",
        entity_uri_key="owner",
        relation="OwnsProperty",
    )
    assert conv is not None
    assert conv.imo == 9074729
    assert conv.lei == "353800ZNORS39N56Y897"
    assert conv.qid == "Q486156"
    r = conv.record
    assert r["v"] == 1
    assert r["relation"] == "OwnsProperty"
    assert r["sourceDid"] == WIKIDATA_SOURCE_DID
    # Subject = LegalEntity URI (LEI-derived rkey, lowercase).
    assert r["subjectUri"].endswith("/corporation-353800znors39n56y897")
    # Object = Vessel feature URI.
    assert r["objectUri"].endswith("/vessel-imo-9074729")
    # registryRef carries QID + label + LEI for traceability.
    assert "Q486156" in r["registryRef"]
    assert "Toyota Tsusho" in r["registryRef"]


def test_operator_binding_produces_Operates_record():
    conv = wikidata_row_to_ownership(
        operator_binding("9012345", "Q41478", "Sony Group", "549300L2BIPCDSRC9T59"),
        entity_lei_key="operatorLEI",
        entity_label_key="operatorLabel",
        entity_uri_key="operator",
        relation="Operates",
    )
    assert conv is not None
    assert conv.record["relation"] == "Operates"


def test_no_lei_falls_back_to_qid_synthetic_uri():
    conv = wikidata_row_to_ownership(
        owner_binding("9999999", "Q999", "Mystery Co"),  # no LEI
        entity_lei_key="ownerLEI",
        entity_label_key="ownerLabel",
        entity_uri_key="owner",
        relation="OwnsProperty",
    )
    assert conv is not None
    assert conv.lei is None
    assert conv.qid == "Q999"
    # Subject URI uses wd-q999 fallback path.
    assert "corporation-wd-q999" in conv.record["subjectUri"]


def test_skips_when_no_imo():
    b = {
        "owner": {"type": "uri", "value": "http://www.wikidata.org/entity/Q1"},
        "ownerLabel": {"type": "literal", "value": "X"},
        "ownerLEI": {"type": "literal", "value": "353800ZNORS39N56Y897"},
    }
    conv = wikidata_row_to_ownership(
        b,
        entity_lei_key="ownerLEI",
        entity_label_key="ownerLabel",
        entity_uri_key="owner",
        relation="OwnsProperty",
    )
    assert conv is None


def test_skips_when_no_lei_and_no_qid():
    b = {
        "imo": {"type": "literal", "value": "9012345"},
        "ownerLabel": {"type": "literal", "value": "Anonymous"},
    }
    conv = wikidata_row_to_ownership(
        b,
        entity_lei_key="ownerLEI",
        entity_label_key="ownerLabel",
        entity_uri_key="owner",
        relation="OwnsProperty",
    )
    assert conv is None


def test_imo_prefix_normalized():
    """Wikidata occasionally returns 'IMO 9074729' instead of bare '9074729'."""
    b = owner_binding("IMO 9074729", "Q486156", "Toyota", "353800ZNORS39N56Y897")
    conv = wikidata_row_to_ownership(
        b,
        entity_lei_key="ownerLEI",
        entity_label_key="ownerLabel",
        entity_uri_key="owner",
        relation="OwnsProperty",
    )
    assert conv is not None
    assert conv.imo == 9074729


def test_rejects_unknown_relation():
    with pytest.raises(ValueError, match="not in KNOWN_RELATIONS"):
        wikidata_row_to_ownership(
            owner_binding("9012345", "Q1", "X", "353800ZNORS39N56Y897"),
            entity_lei_key="ownerLEI",
            entity_label_key="ownerLabel",
            entity_uri_key="owner",
            relation="NotARelation",
        )


def test_caller_can_override_uri_builders():
    conv = wikidata_row_to_ownership(
        owner_binding("9012345", "Q486156", "Toyota", "353800ZNORS39N56Y897"),
        entity_lei_key="ownerLEI",
        entity_label_key="ownerLabel",
        entity_uri_key="owner",
        relation="OwnsProperty",
        opts=OwnershipConverterOptions(
            legal_entity_uri_for_lei=lambda lei: f"at://custom/x/lei-{lei}",
            vessel_uri_for_imo=lambda imo: f"at://custom/y/vessel-{imo}",
        ),
    )
    assert conv.record["subjectUri"] == "at://custom/x/lei-353800ZNORS39N56Y897"
    assert conv.record["objectUri"] == "at://custom/y/vessel-9012345"


# ─── E2E bulk ingest ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_ingest_5_owner_rows_all_succeed():
    captured: list[dict[str, Any]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        captured.append(body)
        return httpx.Response(
            200,
            json={
                "uri": f"at://x/y/z/{len(captured)}",
                "cid": f"bafy-{len(captured)}",
            },
        )

    bindings = [
        owner_binding(f"902345{i}", f"Q{1000+i}", f"Co{i}", "353800ZNORS39N56Y" + str(800 + i).zfill(3))
        for i in range(5)
    ]

    async with _client(handler) as e:
        stats = await ingest_ownership_from_wikidata(
            bindings,
            client=e,
            entity_lei_key="ownerLEI",
            entity_label_key="ownerLabel",
            entity_uri_key="owner",
            relation="OwnsProperty",
        )

    assert stats.total_rows == 5
    assert stats.attempted == 5
    assert stats.ok == 5
    assert stats.failed == 0
    assert len(captured) == 5
    for c in captured:
        assert c["collection"] == OWNERSHIP_COLLECTION
        assert c["record"]["relation"] == "OwnsProperty"
        assert c["record"]["sourceDid"] == WIKIDATA_SOURCE_DID


@pytest.mark.asyncio
async def test_bulk_ingest_mixed_valid_invalid_tracked_separately():
    def handler(req):
        return httpx.Response(200, json={"uri": "at://x/y/z", "cid": "bafy"})

    bindings = [
        owner_binding("9011111", "Q1", "OK1", "353800ZNORS39N56Y100"),
        # No IMO:
        {"owner": {"type": "uri", "value": "http://www.wikidata.org/entity/Q2"}, "ownerLabel": {"type": "literal", "value": "NoIMO"}, "ownerLEI": {"type": "literal", "value": "353800ZNORS39N56Y200"}},
        # No LEI and no QID-derivable identifier (no owner URI):
        {"imo": {"type": "literal", "value": "9033333"}, "ownerLabel": {"type": "literal", "value": "NoIDs"}},
        owner_binding("9044444", "Q4", "OK2", "353800ZNORS39N56Y400"),
    ]

    async with _client(handler) as e:
        stats = await ingest_ownership_from_wikidata(
            bindings, client=e,
            entity_lei_key="ownerLEI",
            entity_label_key="ownerLabel",
            entity_uri_key="owner",
            relation="OwnsProperty",
        )

    assert stats.total_rows == 4
    assert stats.skipped_no_imo == 1
    assert stats.skipped_no_lei_or_qid == 1
    assert stats.attempted == 2
    assert stats.ok == 2


@pytest.mark.asyncio
async def test_bulk_ingest_pds_failure_accumulated_not_thrown():
    call_count = 0

    def handler(req):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return httpx.Response(500, text="upstream broken")
        return httpx.Response(200, json={"uri": "at://x/y/z", "cid": "bafy"})

    bindings = [
        owner_binding(f"9{i:06d}", f"Q{i}", f"Co{i}", "353800ZNORS39N56Y" + str(i).zfill(3))
        for i in range(3)
    ]

    async with _client(handler) as e:
        stats = await ingest_ownership_from_wikidata(
            bindings, client=e,
            entity_lei_key="ownerLEI",
            entity_label_key="ownerLabel",
            entity_uri_key="owner",
            relation="OwnsProperty",
        )

    assert stats.attempted == 3
    assert stats.ok == 2
    assert stats.failed == 1
    assert "upstream broken" in stats.failures[0]["error"]


@pytest.mark.asyncio
async def test_bulk_ingest_fail_fast_after_n():
    def handler(req):
        return httpx.Response(500, text="always fail")

    bindings = [
        owner_binding(f"9{i:06d}", f"Q{i}", f"Co{i}", "353800ZNORS39N56Y" + str(i).zfill(3))
        for i in range(5)
    ]

    async with _client(handler) as e:
        stats = await ingest_ownership_from_wikidata(
            bindings, client=e,
            entity_lei_key="ownerLEI",
            entity_label_key="ownerLabel",
            entity_uri_key="owner",
            relation="OwnsProperty",
            fail_fast_after=1,
        )

    assert stats.attempted == 1
    assert stats.failed == 1


@pytest.mark.asyncio
async def test_operator_relation_path():
    """Operator-side bindings → Operates relation (the new knownValue from
    Phase 3 closure)."""
    captured: list[dict[str, Any]] = []

    def handler(req):
        captured.append(json.loads(req.content))
        return httpx.Response(200, json={"uri": "at://x/y/z", "cid": "bafy"})

    bindings = [
        operator_binding("9056789", "Q41478", "Sony Group", "549300L2BIPCDSRC9T59"),
        operator_binding("9067890", "Q486156", "Toyota Group", "353800ZNORS39N56Y897"),
    ]

    async with _client(handler) as e:
        stats = await ingest_ownership_from_wikidata(
            bindings, client=e,
            entity_lei_key="operatorLEI",
            entity_label_key="operatorLabel",
            entity_uri_key="operator",
            relation="Operates",
        )

    assert stats.ok == 2
    for c in captured:
        assert c["record"]["relation"] == "Operates"
