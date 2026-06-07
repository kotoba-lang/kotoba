"""End-to-end composition test for the corp UBO pipeline.

Per ADR-2605263800 §3 + ADR-2605301600 §3 + ADR-2605312345. Proves the
five independently-built pure pieces actually compose — i.e. the contract
between each stage's output and the next stage's input lines up:

    GLEIF RR golden-copy record
      → gleif_rr_normalize           (#649)   → sensor NDJSON row
      → [L1-join: enrich row jurisdiction from leiReference]   (see note)
      → GleifL2OwnershipSensor        (#309)   → CorpOwnershipObservation
      → ownership_edge_datom          (#312)   → corp.ownershipEdge record
      → ownership_crossref            (#564)   → danjo.crossReferenceLink
    GLEIF L1 record
      → GleifLeiSensor                (stock)  → LeiObservation
      → lei_reference_datom           (#650)   → corp.leiReference entity + CID

CONTRACT FINDING (encoded here, honest): a GLEIF RR record carries NO
jurisdiction (it lives in the L1 entity file), but ownership_edge_datom
requires ``subjectJurisdictionIso3``. So the fetcher MUST join L1
jurisdiction onto each RR row before ownershipEdge datoms can be authored.
This test performs that join explicitly (``_l1_join``) so the gap is
documented rather than latent.
"""

from __future__ import annotations

import json
from pathlib import Path


PROV = dict(
    created_at="2026-05-31T00:00:00Z",
    dataset_pin_at="at://did:web:etzhayyim.com/com.etzhayyim.substrate.datasetPin/g1",
    attesting_did="did:web:corp-sensor.etzhayyim.com",
)

# GLEIF L1 entity fixtures: LEI → (legalName, jurisdictionIso3).
PARENT = "353800OE2WPLLC7YPQ59"   # Sony Group Corporation (JPN)
CHILD = "5493004YDGTGB2VK3O27"    # Sony Semiconductor Solutions Corp (JPN)

LEI_L1_ROWS = [
    {"lei": PARENT, "legalName": "Sony Group Corporation",
     "jurisdictionIso3": "JPN", "registrationStatus": "ISSUED"},
    {"lei": CHILD, "legalName": "Sony Semiconductor Solutions Corporation",
     "jurisdictionIso3": "JPN", "registrationStatus": "ISSUED",
     "parentLei": PARENT, "ultimateParentLei": PARENT},
]

# GLEIF RR golden-copy records: child IS_*_CONSOLIDATED_BY parent.
RR_RECORDS = [
    {"Relationship": {
        "StartNode": {"NodeID": CHILD, "NodeIDType": "LEI"},
        "EndNode": {"NodeID": PARENT, "NodeIDType": "LEI"},
        "RelationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
        "RelationshipStatus": "ACTIVE"},
     "Registration": {"LastUpdateDate": "2025-04-01T00:00:00Z"}},
    {"Relationship": {
        "StartNode": {"NodeID": CHILD, "NodeIDType": "LEI"},
        "EndNode": {"NodeID": PARENT, "NodeIDType": "LEI"},
        "RelationshipType": "IS_ULTIMATELY_CONSOLIDATED_BY",
        "RelationshipStatus": "ACTIVE"},
     "Registration": {"LastUpdateDate": "2025-04-01T00:00:00Z"}},
]


def _stage_shard(tmp_path: Path, subdataset_name: str, lines: list[str]) -> None:
    snap = tmp_path / subdataset_name / "20260531T000000Z"
    snap.mkdir(parents=True)
    (snap / "shard-001.ndjson").write_text("\n".join(lines) + "\n")


def _l1_join(row: dict, l1_by_lei: dict[str, dict]) -> dict:
    """The fetcher's L1-join: stamp jurisdiction onto an RR-derived row.

    RR records have no jurisdiction; ownership_edge_datom requires it. The
    fetcher resolves each endpoint LEI against the L1 entity file.
    """
    enriched = dict(row)
    subj = l1_by_lei.get(row.get("subjectLei", ""))
    own = l1_by_lei.get(row.get("ownerLei", ""))
    if subj:
        enriched["subjectJurisdictionIso3"] = subj["jurisdictionIso3"]
    if own:
        enriched["ownerJurisdictionIso3"] = own["jurisdictionIso3"]
    return enriched


def test_full_ubo_pipeline_composes(tmp_path, load_sensor, make_pin):
    rr_mod = load_sensor("corp.gleif_rr_normalize")
    own_sensor_mod = load_sensor("corp.gleif_l2_ownership_sensor")
    lei_sensor_mod = load_sensor("corp.lei_sensor")
    edge_datom_mod = load_sensor("corp.ownership_edge_datom")
    lei_datom_mod = load_sensor("corp.lei_reference_datom")
    crossref_mod = load_sensor("corp.ownership_crossref")

    l1_by_lei = {r["lei"]: r for r in LEI_L1_ROWS}

    # ── Stage 1: GLEIF RR record → normalized row → L1-join → NDJSON shard.
    rows = list(rr_mod.gleif_rr_records_to_rows(RR_RECORDS))
    assert len(rows) == 2
    joined = [_l1_join(r, l1_by_lei) for r in rows]
    own_sub = "corp/ownership/gleif-l2"
    _stage_shard(tmp_path, own_sub, [json.dumps(r) for r in joined])

    # ── Stage 2: GleifL2OwnershipSensor → CorpOwnershipObservation.
    pin_o, res_o = make_pin(own_sub, license="CC0-1.0", tier="A")
    own_sensor = own_sensor_mod.GleifL2OwnershipSensor(
        annex_root=tmp_path, pin_resolver=res_o)
    observations = list(own_sensor.stream(own_sensor.latest_pin()))
    assert len(observations) == 2
    kinds = {o.ownership_kind for o in observations}
    assert kinds == {"parent-subsidiary", "control-relationship"}
    # The L1-join populated jurisdiction (RR had none).
    assert all(o.subject_jurisdiction_iso3 == "JPN" for o in observations)

    # ── Stage A: GLEIF L1 → LeiObservation → corp.leiReference + CID map.
    lei_sub = "corp/lei/gleif/lei-l1"
    _stage_shard(tmp_path, lei_sub, [json.dumps(r) for r in LEI_L1_ROWS])
    pin_l, res_l = make_pin(lei_sub, license="CC0-1.0", tier="A")
    lei_sensor = lei_sensor_mod.GleifLeiSensor(
        annex_root=tmp_path, pin_resolver=res_l)
    lei_obs = list(lei_sensor.stream(lei_sensor.latest_pin()))
    assert {o.entity_lei for o in lei_obs} == {PARENT, CHILD}
    lei_reference_cids = {}
    for lo in lei_obs:
        rec = lei_datom_mod.observation_to_lei_record(lo, **PROV)
        lei_reference_cids[rec["entityLei"]] = lei_datom_mod.lei_record_id(rec)

    # ── Stage 3: observation → corp.ownershipEdge record (+ id as CID).
    edge_pairs = []
    for obs in observations:
        rec = edge_datom_mod.observation_to_edge_record(obs, **PROV)  # no raise
        edge_pairs.append((rec, edge_datom_mod.edge_record_id(rec)))
    assert len(edge_pairs) == 2

    # ── Stage 4: ownershipEdge → danjo.crossReferenceLink (cite LEI basis).
    links = crossref_mod.ownership_edges_to_crossref_links(
        edge_pairs,
        created_at=PROV["created_at"],
        source_cell_did="did:web:danjo.etzhayyim.com",
        attesting_did=PROV["attesting_did"],
        lei_reference_cids=lei_reference_cids,
    )
    # Both edges now map (entity-control-edge added in #564 completion).
    assert {l["linkType"] for l in links} == {
        "entity-parent-subsidiary-edge", "entity-control-edge"}

    # ── Cross-stage contract: each link cites its edge CID + BOTH endpoint
    #    leiReference CIDs (entity resolution wired end-to-end).
    for link in links:
        assert link["fromRef"] == PARENT   # owner = parent
        assert link["toRef"] == CHILD      # subject = child
        assert lei_reference_cids[PARENT] in link["basisRecordCids"]
        assert lei_reference_cids[CHILD] in link["basisRecordCids"]
        # The edge record's own id is the first basis CID.
        assert link["basisRecordCids"][0].startswith(
            "com.etzhayyim.corp.ownershipEdge:gleif-l2:")
        assert link["confidence"] == "registry-asserted"
        assert link["jurisdiction"] == "JPN"
