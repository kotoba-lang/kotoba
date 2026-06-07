"""Tests for corp.gleif_rr_normalize — GLEIF RR-CDF record → sensor row.

Per ADR-2605263800 §3. Validates:

1. A well-formed consolidation record maps to the sensor row shape with
   the correct direction (subject = StartNode child, owner = EndNode parent).
2. RelationshipStatus / LastUpdateDate / quantifier-percentage pass-through.
3. G7 skips: missing Relationship, non-LEI endpoints, malformed LEI,
   missing RelationshipType.
4. NDJSON rendering: one JSON object per line; rows carry exactly the keys
   GleifL2OwnershipSensor reads (contract check, without importing it).
"""

from __future__ import annotations

import json


def _rr(start, end, rel_type="IS_DIRECTLY_CONSOLIDATED_BY", **extra):
    rel = {
        "StartNode": {"NodeID": start, "NodeIDType": "LEI"},
        "EndNode": {"NodeID": end, "NodeIDType": "LEI"},
        "RelationshipType": rel_type,
        "RelationshipStatus": extra.pop("status", "ACTIVE"),
    }
    rel.update(extra.pop("rel", {}))
    rec = {"Relationship": rel}
    reg = extra.pop("registration", None)
    if reg is not None:
        rec["Registration"] = reg
    return rec


SUB = "5493004YDGTGB2VK3O27"
OWN = "353800OE2WPLLC7YPQ59"


def test_consolidation_record_maps_with_direction(load_sensor):
    mod = load_sensor("corp.gleif_rr_normalize")
    rec = _rr(SUB, OWN, registration={"LastUpdateDate": "2025-04-01T00:00:00Z"})
    row = mod.normalize_gleif_rr_record(rec)
    assert row["subjectLei"] == SUB   # StartNode = consolidated child
    assert row["ownerLei"] == OWN     # EndNode = consolidating parent
    assert row["relationshipType"] == "IS_DIRECTLY_CONSOLIDATED_BY"
    assert row["relationshipStatus"] == "ACTIVE"
    assert row["asOf"] == "2025-04-01T00:00:00Z"
    assert "pctHeld" not in row  # no quantifier on this edge


def test_quantifier_percentage_passthrough(load_sensor):
    mod = load_sensor("corp.gleif_rr_normalize")
    rec = _rr(
        SUB, OWN, rel_type="IS_ULTIMATELY_CONSOLIDATED_BY",
        rel={"RelationshipQuantifiers": [
            {"QuantifierAmount": "75.5", "MeasurementMethod": "ACCOUNTING_CONSOLIDATION"}
        ]},
    )
    row = mod.normalize_gleif_rr_record(rec)
    assert row["pctHeld"] == 75.5
    # Non-numeric / out-of-range quantifier ignored.
    bad = _rr(SUB, OWN, rel={"RelationshipQuantifiers": [{"QuantifierAmount": "n/a"}]})
    assert "pctHeld" not in mod.normalize_gleif_rr_record(bad)
    over = _rr(SUB, OWN, rel={"RelationshipQuantifiers": [{"QuantifierAmount": "150"}]})
    assert "pctHeld" not in mod.normalize_gleif_rr_record(over)


def test_g7_skips(load_sensor):
    mod = load_sensor("corp.gleif_rr_normalize")
    # No Relationship.
    assert mod.normalize_gleif_rr_record({"Registration": {}}) is None
    # Non-LEI node type.
    rec = _rr(SUB, OWN)
    rec["Relationship"]["EndNode"]["NodeIDType"] = "BIC"
    assert mod.normalize_gleif_rr_record(rec) is None
    # Malformed (short) LEI.
    assert mod.normalize_gleif_rr_record(_rr(SUB, "TOOSHORT")) is None
    # Missing RelationshipType.
    rec2 = _rr(SUB, OWN, rel_type="")
    assert mod.normalize_gleif_rr_record(rec2) is None
    # Not a dict.
    assert mod.normalize_gleif_rr_record("nope") is None


def test_ndjson_and_sensor_key_contract(load_sensor):
    mod = load_sensor("corp.gleif_rr_normalize")
    records = [
        _rr(SUB, OWN, registration={"LastUpdateDate": "2025-04-01T00:00:00Z"}),
        _rr(SUB, "TOOSHORT"),  # skipped
        _rr("549300JM3RYS3WXSML22", OWN, rel_type="IS_ULTIMATELY_CONSOLIDATED_BY"),
    ]
    ndjson = mod.gleif_rr_records_to_ndjson(records)
    lines = [l for l in ndjson.splitlines() if l.strip()]
    assert len(lines) == 2  # 1 G7 skip
    rows = [json.loads(l) for l in lines]
    # Contract: every emitted row carries exactly the keys the sensor reads.
    # (GleifL2OwnershipSensor: subjectLei, ownerLei, relationshipType,
    #  relationshipStatus, optional pctHeld/asOf.)
    allowed = {"subjectLei", "ownerLei", "relationshipType",
               "relationshipStatus", "pctHeld", "asOf"}
    required = {"subjectLei", "ownerLei", "relationshipType"}
    for r in rows:
        assert required <= set(r.keys())
        assert set(r.keys()) <= allowed
        assert len(r["subjectLei"]) == 20 and len(r["ownerLei"]) == 20


def test_empty_input_yields_empty_ndjson(load_sensor):
    mod = load_sensor("corp.gleif_rr_normalize")
    assert mod.gleif_rr_records_to_ndjson([]) == ""
    assert list(mod.gleif_rr_records_to_rows([])) == []
