"""Tests for corp.ownership_crossref — corp.ownershipEdge record →
``com.etzhayyim.danjo.crossReferenceLink`` (the pure crossref core).

Per ADR-2605263800 §3 + ADR-2605301600 §3. Validates:

1. ownershipKind → linkType mapping (ubo / parent-subsidiary / officer).
2. SKIP for kinds with no Lexicon linkType (control-relationship,
   direct-shareholder) — no invented values.
3. Direction (fromRef = owner, toRef = subject), confidence, jurisdiction.
4. basisRecordCids cite the edge CID + optional leiReference CIDs.
5. Under-provenanced / endpoint-missing / basis-missing edges → skip.
6. Batch never raises; order preserved.
"""

from __future__ import annotations

PROV = dict(
    created_at="2026-05-31T00:00:00Z",
    source_cell_did="did:web:danjo.etzhayyim.com",
    attesting_did="did:web:corp-sensor.etzhayyim.com",
)


def _edge(**overrides):
    """A minimal corp.ownershipEdge record (Lexicon shape)."""
    rec = {
        "createdAt": "2026-05-31T00:00:00Z",
        "subjectJurisdictionIso3": "JPN",
        "ownershipKind": "parent-subsidiary",
        "sourceId": "gleif-l2",
        "datasetPinAt": "at://did:web:etzhayyim.com/x/abc",
        "tier": "A",
        "license": "CC0-1.0",
        "attestingDid": "did:web:corp-sensor.etzhayyim.com",
        "subjectLei": "5493004YDGTGB2VK3O27",
        "ownerLei": "353800OE2WPLLC7YPQ59",
    }
    rec.update(overrides)
    return rec


def test_parent_subsidiary_link(load_sensor):
    mod = load_sensor("corp.ownership_crossref")
    link = mod.ownership_edge_to_crossref_link(_edge(), "cid:edge1", **PROV)
    assert link is not None
    assert link["linkType"] == "entity-parent-subsidiary-edge"
    # Direction: owner → subject.
    assert link["fromRef"] == "353800OE2WPLLC7YPQ59"
    assert link["toRef"] == "5493004YDGTGB2VK3O27"
    assert link["confidence"] == "registry-asserted"
    assert link["jurisdiction"] == "JPN"
    assert link["basisRecordCids"] == ["cid:edge1"]
    assert mod.CROSSREF_LINK_NSID == "com.etzhayyim.danjo.crossReferenceLink"


def test_ubo_and_officer_link_types(load_sensor):
    mod = load_sensor("corp.ownership_crossref")
    ubo = mod.ownership_edge_to_crossref_link(
        _edge(ownershipKind="ubo"), "cid:e", **PROV
    )
    officer = mod.ownership_edge_to_crossref_link(
        _edge(ownershipKind="officer"), "cid:e", **PROV
    )
    assert ubo["linkType"] == "entity-ubo-edge"
    assert officer["linkType"] == "entity-officer-edge"


def test_all_ownership_kinds_map(load_sensor):
    mod = load_sensor("corp.ownership_crossref")
    # All five OwnershipKind values now have a Lexicon linkType.
    expected = {
        "ubo": "entity-ubo-edge",
        "direct-shareholder": "entity-direct-shareholder-edge",
        "parent-subsidiary": "entity-parent-subsidiary-edge",
        "control-relationship": "entity-control-edge",
        "officer": "entity-officer-edge",
    }
    for kind, link_type in expected.items():
        link = mod.ownership_edge_to_crossref_link(
            _edge(ownershipKind=kind), "cid:e", **PROV
        )
        assert link is not None, kind
        assert link["linkType"] == link_type
    # An out-of-enum kind is still skipped (no invented linkType).
    assert mod.ownership_edge_to_crossref_link(
        _edge(ownershipKind="not-a-real-kind"), "cid:e", **PROV
    ) is None


def test_basis_includes_lei_reference_cids(load_sensor):
    mod = load_sensor("corp.ownership_crossref")
    refs = {
        "353800OE2WPLLC7YPQ59": "cid:lei-owner",
        "5493004YDGTGB2VK3O27": "cid:lei-subject",
    }
    link = mod.ownership_edge_to_crossref_link(
        _edge(), "cid:edge1", lei_reference_cids=refs, **PROV
    )
    assert link["basisRecordCids"][0] == "cid:edge1"
    assert "cid:lei-owner" in link["basisRecordCids"]
    assert "cid:lei-subject" in link["basisRecordCids"]
    # minLength 1 always satisfied; edge CID always first.
    assert len(link["basisRecordCids"]) == 3


def test_missing_endpoint_or_basis_skipped(load_sensor):
    mod = load_sensor("corp.ownership_crossref")
    # No owner LEI / local id → skip.
    e = _edge()
    del e["ownerLei"]
    assert mod.ownership_edge_to_crossref_link(e, "cid:e", **PROV) is None
    # Empty basis CID → skip (can't cite the public basis).
    assert mod.ownership_edge_to_crossref_link(_edge(), "", **PROV) is None
    # Missing provenance → skip.
    assert mod.ownership_edge_to_crossref_link(
        _edge(), "cid:e",
        created_at="", source_cell_did=PROV["source_cell_did"],
        attesting_did=PROV["attesting_did"],
    ) is None


def test_local_id_endpoints(load_sensor):
    mod = load_sensor("corp.ownership_crossref")
    # No LEIs but local ids present → still links (registry-asserted).
    e = _edge(ownershipKind="officer")
    del e["subjectLei"]
    del e["ownerLei"]
    e["subjectLocalId"] = "E01777"
    e["ownerLocalId"] = "E99999"
    link = mod.ownership_edge_to_crossref_link(e, "cid:e", **PROV)
    assert link["fromRef"] == "E99999"
    assert link["toRef"] == "E01777"


def test_batch_skips_and_preserves_order(load_sensor):
    mod = load_sensor("corp.ownership_crossref")
    edges = [
        (_edge(ownershipKind="ubo"), "cid:1"),
        (_edge(ownershipKind="not-a-real-kind"), "cid:2"),  # skip (out-of-enum)
        (_edge(ownershipKind="control-relationship"), "cid:3"),
    ]
    links = mod.ownership_edges_to_crossref_links(edges, **PROV)
    assert len(links) == 2
    assert [l["linkType"] for l in links] == [
        "entity-ubo-edge",
        "entity-control-edge",
    ]
