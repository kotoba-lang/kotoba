"""Tests for corp.lei_reference_datom — LeiObservation →
``com.etzhayyim.corp.leiReference`` record + kotoba EAVT ingest batch.

Per ADR-2605263800 §3 + ADR-2605312345. Validates:

1. Lexicon record shape: required fields populated; parent pointers
   included only when published.
2. STRICT authoring: missing required field raises ValueError.
3. kotoba entity envelope: {id, type, labelEn, claims=[{pred,value}]} with
   ``lei/<camelField>`` predicates; entity id is the LEI (canonical key).
4. Batch G7 discipline: invalid rows skipped; duplicate LEIs de-duplicated.
"""

from __future__ import annotations

import pytest

PROV = dict(
    created_at="2026-05-31T00:00:00Z",
    dataset_pin_at="at://did:web:etzhayyim.com/com.etzhayyim.substrate.datasetPin/g1",
    attesting_did="did:web:corp-sensor.etzhayyim.com",
)


def _obs(corp_base_module, **overrides):
    defaults = dict(
        sensor="corp/lei/gleif/lei-l1",
        tier="A",
        pin_revision="sha256:test",
        entity_lei="353800OE2WPLLC7YPQ59",
        legal_name="Sony Group Corporation",
        jurisdiction_iso3="JPN",
        registration_status="ISSUED",
        parent_lei=None,
        ultimate_parent_lei=None,
        license_tag="CC0-1.0",
    )
    defaults.update(overrides)
    return corp_base_module.LeiObservation(**defaults)


def test_lei_record_shape(load_sensor, corp_base_module):
    mod = load_sensor("corp.lei_reference_datom")
    rec = mod.observation_to_lei_record(_obs(corp_base_module), **PROV)
    for f in ("createdAt", "entityLei", "legalName", "jurisdictionIso3",
              "registrationStatus", "datasetPinAt", "tier", "license",
              "attestingDid"):
        assert rec[f]
    assert rec["entityLei"] == "353800OE2WPLLC7YPQ59"
    assert rec["legalName"] == "Sony Group Corporation"
    assert rec["jurisdictionIso3"] == "JPN"
    assert rec["tier"] == "A"
    assert rec["license"] == "CC0-1.0"
    # No parent pointers on this row.
    assert "parentLei" not in rec
    assert "ultimateParentLei" not in rec
    assert mod.LEI_REFERENCE_NSID == "com.etzhayyim.corp.leiReference"


def test_parent_pointers_included_when_published(load_sensor, corp_base_module):
    mod = load_sensor("corp.lei_reference_datom")
    rec = mod.observation_to_lei_record(
        _obs(corp_base_module,
             entity_lei="5493004YDGTGB2VK3O27",
             legal_name="Sony Semiconductor Solutions Corp",
             parent_lei="353800OE2WPLLC7YPQ59",
             ultimate_parent_lei="353800OE2WPLLC7YPQ59"),
        **PROV,
    )
    assert rec["parentLei"] == "353800OE2WPLLC7YPQ59"
    assert rec["ultimateParentLei"] == "353800OE2WPLLC7YPQ59"


def test_missing_required_raises(load_sensor, corp_base_module):
    mod = load_sensor("corp.lei_reference_datom")
    # Empty legal name → required field missing.
    with pytest.raises(ValueError) as ei:
        mod.observation_to_lei_record(_obs(corp_base_module, legal_name=""), **PROV)
    assert "legalName" in str(ei.value)
    # Empty provenance also caught.
    with pytest.raises(ValueError):
        mod.observation_to_lei_record(
            _obs(corp_base_module),
            created_at="", dataset_pin_at=PROV["dataset_pin_at"],
            attesting_did=PROV["attesting_did"],
        )


def test_kotoba_entity_shape_and_id(load_sensor, corp_base_module):
    mod = load_sensor("corp.lei_reference_datom")
    ent = mod.observation_to_kotoba_entity(_obs(corp_base_module), **PROV)
    assert ent["type"] == "CorpLeiReference"
    # Entity id is the LEI (canonical key) — stable across re-ingest.
    assert ent["id"] == "com.etzhayyim.corp.leiReference:353800OE2WPLLC7YPQ59"
    preds = {c["pred"]: c["value"] for c in ent["claims"]}
    assert preds["lei/entityLei"] == "353800OE2WPLLC7YPQ59"
    assert preds["lei/legalName"] == "Sony Group Corporation"
    assert preds["lei/jurisdictionIso3"] == "JPN"
    assert preds["lei/datasetPinAt"] == PROV["dataset_pin_at"]
    assert all(isinstance(c["value"], str) for c in ent["claims"])


def test_batch_skips_invalid_and_dedupes(load_sensor, corp_base_module):
    mod = load_sensor("corp.lei_reference_datom")
    good = _obs(corp_base_module)
    dup = _obs(corp_base_module)  # same LEI → de-duped
    other = _obs(corp_base_module, entity_lei="HWUPKR0MPOU8FGXBT394",
                 legal_name="Apple Inc.", jurisdiction_iso3="USA")
    bad = _obs(corp_base_module, registration_status="")  # G7 skip
    batch = mod.observations_to_kotoba_batch([good, dup, other, bad], **PROV)
    ids = [e["id"] for e in batch["entities"]]
    assert len(ids) == 2  # dup collapsed, bad skipped
    assert len(set(ids)) == 2
    assert "com.etzhayyim.corp.leiReference:HWUPKR0MPOU8FGXBT394" in ids


def test_id_stable_across_reingest(load_sensor, corp_base_module):
    mod = load_sensor("corp.lei_reference_datom")
    # Same LEI, later snapshot with a status change → SAME entity id
    # (new facts append onto the entity; history preserved on the log).
    a = mod.observation_to_kotoba_entity(_obs(corp_base_module), **PROV)
    b = mod.observation_to_kotoba_entity(
        _obs(corp_base_module, registration_status="LAPSED"),
        created_at="2027-01-01T00:00:00Z",
        dataset_pin_at=PROV["dataset_pin_at"],
        attesting_did=PROV["attesting_did"],
    )
    assert a["id"] == b["id"]
