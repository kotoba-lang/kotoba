"""Tests for corp.ownership_edge_datom — CorpOwnershipObservation →
``com.etzhayyim.corp.ownershipEdge`` record + kotoba EAVT ingest batch.

Per ADR-2605263800 §3 + ADR-2605312345. Validates:

1. Lexicon record shape: required fields populated from observation +
   caller-supplied provenance; optional fields included only when set.
2. pctHeld unit conversion: percentage [0,100] → basis points [0,10000],
   with clamping; control-edge / officer → no pctHeld.
3. STRICT authoring: missing required Lexicon field raises ValueError.
4. kotoba entity envelope: {id, type, labelEn, claims=[{pred,value}]} with
   ``ownership/<camelField>`` predicates and stringified values
   (the shape danjo/kanae read).
5. Batch G7 discipline: invalid rows skipped (not raised); duplicate
   edges de-duplicated; deterministic entity ids.
6. sourceId derivation from the sensor subdataset name.
"""

from __future__ import annotations

import pytest


PROV = dict(
    created_at="2026-05-31T00:00:00Z",
    dataset_pin_at="at://did:web:etzhayyim.com/com.etzhayyim.substrate.datasetPin/abc123",
    attesting_did="did:web:corp-sensor.etzhayyim.com",
)


def _obs(corp_base_module, **overrides):
    """Build a CorpOwnershipObservation with sensible defaults."""
    defaults = dict(
        sensor="corp/ownership/gleif-l2",
        tier="A",
        pin_revision="sha256:test",
        subject_lei="5493004YDGTGB2VK3O27",
        subject_local_id=None,
        subject_jurisdiction_iso3="JPN",
        owner_lei="353800OE2WPLLC7YPQ59",
        owner_local_id=None,
        owner_jurisdiction_iso3="JPN",
        ownership_kind="control-relationship",
        pct_held=None,
        as_of="2025-04-01",
        license_tag="CC0-1.0",
    )
    defaults.update(overrides)
    return corp_base_module.CorpOwnershipObservation(**defaults)


def test_control_edge_record_shape(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    obs = _obs(corp_base_module)  # control-relationship, no pct
    rec = mod.observation_to_edge_record(obs, **PROV)
    # Required Lexicon fields present.
    for f in ("createdAt", "subjectJurisdictionIso3", "ownershipKind",
              "sourceId", "datasetPinAt", "tier", "license", "attestingDid"):
        assert rec[f]
    assert rec["ownershipKind"] == "control-relationship"
    assert rec["sourceId"] == "gleif-l2"  # derived from sensor name
    assert rec["subjectLei"] == "5493004YDGTGB2VK3O27"
    assert rec["ownerLei"] == "353800OE2WPLLC7YPQ59"
    # Control edge carries no percentage.
    assert "pctHeld" not in rec
    assert rec["license"] == "CC0-1.0"
    assert mod.OWNERSHIP_EDGE_NSID == "com.etzhayyim.corp.ownershipEdge"


def test_pct_held_to_basis_points(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    obs = _obs(corp_base_module, ownership_kind="direct-shareholder", pct_held=75.0)
    rec = mod.observation_to_edge_record(obs, **PROV)
    assert rec["pctHeld"] == 7500  # 75% → 7500 bp
    # Fractional percent.
    rec2 = mod.observation_to_edge_record(
        _obs(corp_base_module, ownership_kind="ubo", pct_held=33.33), **PROV
    )
    assert rec2["pctHeld"] == 3333


def test_pct_held_clamped(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    hi = mod.observation_to_edge_record(
        _obs(corp_base_module, ownership_kind="ubo", pct_held=150.0), **PROV
    )
    lo = mod.observation_to_edge_record(
        _obs(corp_base_module, ownership_kind="ubo", pct_held=-5.0), **PROV
    )
    assert hi["pctHeld"] == 10000
    assert lo["pctHeld"] == 0


def test_missing_required_raises(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    # Empty subject jurisdiction → required field missing.
    obs = _obs(corp_base_module, subject_jurisdiction_iso3="")
    with pytest.raises(ValueError) as ei:
        mod.observation_to_edge_record(obs, **PROV)
    assert "subjectJurisdictionIso3" in str(ei.value)
    # Empty provenance also caught.
    with pytest.raises(ValueError):
        mod.observation_to_edge_record(
            _obs(corp_base_module),
            created_at="", dataset_pin_at=PROV["dataset_pin_at"],
            attesting_did=PROV["attesting_did"],
        )


def test_kotoba_entity_shape(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    ent = mod.observation_to_kotoba_entity(_obs(corp_base_module), **PROV)
    assert ent["type"] == "CorpOwnershipEdge"
    assert ent["id"].startswith("com.etzhayyim.corp.ownershipEdge:gleif-l2:")
    # Claims are {pred, value} with camelCase ownership/ predicates, str values.
    preds = {c["pred"]: c["value"] for c in ent["claims"]}
    assert preds["ownership/ownershipKind"] == "control-relationship"
    assert preds["ownership/subjectLei"] == "5493004YDGTGB2VK3O27"
    assert preds["ownership/datasetPinAt"] == PROV["dataset_pin_at"]
    assert preds["ownership/attestingDid"] == PROV["attesting_did"]
    assert all(isinstance(c["value"], str) for c in ent["claims"])
    # No pctHeld claim for a control edge.
    assert "ownership/pctHeld" not in preds


def test_batch_skips_invalid_and_dedupes(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    good = _obs(corp_base_module)
    dup = _obs(corp_base_module)  # identical edge → same id, de-duped
    other = _obs(
        corp_base_module, ownership_kind="parent-subsidiary",
        subject_lei="549300JM3RYS3WXSML22",
    )
    bad = _obs(corp_base_module, subject_jurisdiction_iso3="")  # G7 skip
    batch = mod.observations_to_kotoba_batch([good, dup, other, bad], **PROV)
    ents = batch["entities"]
    assert len(ents) == 2  # dup collapsed, bad skipped
    ids = [e["id"] for e in ents]
    assert len(set(ids)) == 2
    kinds = {
        c["value"]
        for e in ents for c in e["claims"]
        if c["pred"] == "ownership/ownershipKind"
    }
    assert kinds == {"control-relationship", "parent-subsidiary"}


def test_entity_id_deterministic_and_history_distinct(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    a = mod.observation_to_kotoba_entity(_obs(corp_base_module), **PROV)
    b = mod.observation_to_kotoba_entity(_obs(corp_base_module), **PROV)
    assert a["id"] == b["id"]  # same edge → stable id
    # A later-dated observation of the same pair is a distinct edge fact.
    later = mod.observation_to_kotoba_entity(
        _obs(corp_base_module, as_of="2026-04-01"), **PROV
    )
    assert later["id"] != a["id"]


def test_source_id_derivation(load_sensor, corp_base_module):
    mod = load_sensor("corp.ownership_edge_datom")
    oc = mod.observation_to_edge_record(
        _obs(corp_base_module, sensor="corp/ownership/opencorporates-opendata",
             tier="B", license_tag="CC-BY-SA-4.0"),
        **PROV,
    )
    assert oc["sourceId"] == "opencorporates-opendata"
    assert oc["tier"] == "B"
