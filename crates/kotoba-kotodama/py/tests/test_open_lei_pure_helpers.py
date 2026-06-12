"""Tests for pure helpers in open_lei.py: _as_list, _str_list, _utc_now, gleif_manifest_plan,
normalize_lei_record, gleif_bulk_collect (plan mode), gleif_record_normalize, gleif_ems_match."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import open_lei as OL


# ─── _utc_now ────────────────────────────────────────────────────────────────

def test_utc_now_ends_with_z() -> None:
    assert OL._utc_now().endswith("Z")


def test_utc_now_matches_pattern() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", OL._utc_now())


# ─── _as_list ────────────────────────────────────────────────────────────────

def test_as_list_passthrough_list() -> None:
    lst = [1, 2, 3]
    assert OL._as_list(lst) is lst


def test_as_list_none_returns_empty() -> None:
    assert OL._as_list(None) == []


def test_as_list_string_returns_empty() -> None:
    assert OL._as_list("hello") == []


def test_as_list_dict_returns_empty() -> None:
    assert OL._as_list({"a": 1}) == []


def test_as_list_int_returns_empty() -> None:
    assert OL._as_list(42) == []


def test_as_list_empty_list_returns_empty_list() -> None:
    assert OL._as_list([]) == []


# ─── _str_list ───────────────────────────────────────────────────────────────

def test_str_list_converts_items_to_str() -> None:
    result = OL._str_list([1, 2, 3])
    assert result == ["1", "2", "3"]


def test_str_list_filters_falsy() -> None:
    result = OL._str_list([0, "", None, "x"])
    assert result == ["x"]


def test_str_list_non_list_returns_empty() -> None:
    assert OL._str_list(None) == []
    assert OL._str_list("foo") == []


def test_str_list_preserves_strings() -> None:
    result = OL._str_list(["a", "b", "c"])
    assert result == ["a", "b", "c"]


# ─── gleif_manifest_plan ─────────────────────────────────────────────────────

def test_gleif_manifest_plan_returns_dict() -> None:
    result = OL.gleif_manifest_plan()
    assert isinstance(result, dict)
    assert "openLeiGleifManifestPlan" in result


def test_gleif_manifest_plan_default_datasets() -> None:
    plan = OL.gleif_manifest_plan()["openLeiGleifManifestPlan"]
    kinds = {d["datasetKind"] for d in plan["datasets"]}
    assert "lei-cdf" in kinds
    assert "rr-cdf" in kinds
    assert "reporting-exception" in kinds


def test_gleif_manifest_plan_custom_as_of_date() -> None:
    plan = OL.gleif_manifest_plan(as_of_date="2026-01-15")["openLeiGleifManifestPlan"]
    assert plan["asOfDate"] == "2026-01-15"
    assert "2026-01-15" in plan["manifestId"]


def test_gleif_manifest_plan_custom_datasets() -> None:
    plan = OL.gleif_manifest_plan(datasets=["lei-cdf"])["openLeiGleifManifestPlan"]
    assert len(plan["datasets"]) == 1
    assert plan["datasets"][0]["datasetKind"] == "lei-cdf"


def test_gleif_manifest_plan_invalid_dataset_skipped() -> None:
    plan = OL.gleif_manifest_plan(datasets=["lei-cdf", "nonexistent"])["openLeiGleifManifestPlan"]
    assert len(plan["datasets"]) == 1


def test_gleif_manifest_plan_valid_modes() -> None:
    for mode in ["delta", "backfill", "repair", "verify"]:
        plan = OL.gleif_manifest_plan(mode=mode)["openLeiGleifManifestPlan"]
        assert plan["mode"] == mode


def test_gleif_manifest_plan_invalid_mode_defaults_to_delta() -> None:
    plan = OL.gleif_manifest_plan(mode="invalid")["openLeiGleifManifestPlan"]
    assert plan["mode"] == "delta"


def test_gleif_manifest_plan_has_terms() -> None:
    plan = OL.gleif_manifest_plan()["openLeiGleifManifestPlan"]
    assert isinstance(plan["terms"], list)
    assert len(plan["terms"]) > 0


def test_gleif_manifest_plan_partition_key_has_date() -> None:
    plan = OL.gleif_manifest_plan(as_of_date="2026-04-01")["openLeiGleifManifestPlan"]
    for dataset in plan["datasets"]:
        assert "2026-04-01" in dataset["partitionKey"]


# ─── gleif_bulk_collect (plan mode, no HTTP) ─────────────────────────────────

def test_gleif_bulk_collect_plan_mode_returns_dict() -> None:
    result = OL.gleif_bulk_collect(fetch=False)
    assert isinstance(result, dict)
    assert "openLeiGleifBulkCollect" in result


def test_gleif_bulk_collect_plan_mode_no_records() -> None:
    body = OL.gleif_bulk_collect(fetch=False)["openLeiGleifBulkCollect"]
    assert body["fetchMode"] == "plan"
    assert "records" not in body


def test_gleif_bulk_collect_plan_dataset_kind() -> None:
    body = OL.gleif_bulk_collect(fetch=False, dataset_kind="rr-cdf")["openLeiGleifBulkCollect"]
    assert body["datasetKind"] == "rr-cdf"


def test_gleif_bulk_collect_plan_shard_clamped() -> None:
    body = OL.gleif_bulk_collect(fetch=False, shard=-5)["openLeiGleifBulkCollect"]
    assert body["shard"] == 0


def test_gleif_bulk_collect_plan_shard_count_minimum_1() -> None:
    body = OL.gleif_bulk_collect(fetch=False, shard_count=0)["openLeiGleifBulkCollect"]
    assert body["shardCount"] >= 1


def test_gleif_bulk_collect_plan_as_of_date() -> None:
    body = OL.gleif_bulk_collect(fetch=False, as_of_date="2026-03-10")["openLeiGleifBulkCollect"]
    assert body["asOfDate"] == "2026-03-10"


def test_gleif_bulk_collect_unsupported_dataset_when_fetching() -> None:
    # reporting-exception has no bulk paginated API endpoint — remains unsupported
    body = OL.gleif_bulk_collect(fetch=True, dataset_kind="reporting-exception")["openLeiGleifBulkCollect"]
    assert body["fetchMode"] == "unsupported"
    assert body["fetchSupported"] is False
    assert body["records"] == []


# ─── normalize_lei_record ────────────────────────────────────────────────────

def test_normalize_lei_record_basic() -> None:
    record = {
        "attributes": {
            "lei": "ABCD12345",
            "entity": {
                "legalName": {"name": "Acme Corp"},
                "legalAddress": {"country": "JP"},
            },
            "registration": {
                "status": "ISSUED",
                "initialRegistrationDate": "2020-01-01",
                "nextRenewalDate": "2027-01-01",
            },
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["lei"] == "ABCD12345"
    assert result["legal_name"] == "Acme Corp"
    assert result["country"] == "JP"
    assert result["status"] == "active"


def test_normalize_lei_record_vertex_id_format() -> None:
    record = {"attributes": {"lei": "LEI001"}}
    result = OL.normalize_lei_record(record)
    assert result["vertex_id"].startswith("at://did:web:open-lei.etzhayyim.com/")
    assert "LEI001" in result["vertex_id"]


def test_normalize_lei_record_lapsed_when_not_issued() -> None:
    record = {
        "attributes": {
            "lei": "X001",
            "registration": {"status": "LAPSED"},
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["status"] == "lapsed"


def test_normalize_lei_record_unknown_status_when_missing() -> None:
    record = {"attributes": {"lei": "X002"}}
    result = OL.normalize_lei_record(record)
    assert result["registration_status"] == "UNKNOWN"


def test_normalize_lei_record_flat_format() -> None:
    record = {"id": "FLAT001", "legalName": "Flat Corp"}
    result = OL.normalize_lei_record(record)
    assert result["lei"] == "FLAT001"
    assert result["legal_name"] == "Flat Corp"


def test_normalize_lei_record_has_required_keys() -> None:
    record = {"attributes": {"lei": "K001"}}
    result = OL.normalize_lei_record(record)
    for key in ["vertex_id", "lei", "legal_name", "country", "status", "created_at", "owner_did"]:
        assert key in result


# ─── gleif_record_normalize ──────────────────────────────────────────────────

def test_gleif_record_normalize_empty_records() -> None:
    result = OL.gleif_record_normalize(records=[])
    body = result["openLeiGleifRecordNormalize"]
    assert body["recordsRead"] == 0
    assert body["entityRows"] == []


def test_gleif_record_normalize_lei_cdf_normalizes_records() -> None:
    records = [{"attributes": {"lei": "R001", "entity": {}, "registration": {}}}]
    body = OL.gleif_record_normalize(dataset_kind="lei-cdf", records=records)["openLeiGleifRecordNormalize"]
    assert body["recordsRead"] == 1
    assert len(body["entityRows"]) == 1


def test_gleif_record_normalize_rr_cdf_no_entity_rows() -> None:
    records = [{"attributes": {"lei": "R002"}}]
    body = OL.gleif_record_normalize(dataset_kind="rr-cdf", records=records)["openLeiGleifRecordNormalize"]
    assert body["entityRows"] == []
    assert len(body["ownershipRows"]) == 1


def test_gleif_record_normalize_reporting_exception() -> None:
    records = [{"attributes": {"lei": "R003"}}]
    body = OL.gleif_record_normalize(dataset_kind="reporting-exception", records=records)["openLeiGleifRecordNormalize"]
    assert body["entityRows"] == []
    assert len(body["reportingExceptionRows"]) == 1


def test_gleif_record_normalize_as_of_date() -> None:
    body = OL.gleif_record_normalize(as_of_date="2026-01-01", records=[])["openLeiGleifRecordNormalize"]
    assert body["asOfDate"] == "2026-01-01"


def test_gleif_record_normalize_skips_non_dict_items() -> None:
    records = [{"attributes": {"lei": "R001"}}, "bad-item", 42]
    body = OL.gleif_record_normalize(dataset_kind="lei-cdf", records=records)["openLeiGleifRecordNormalize"]
    assert body["recordsRead"] == 1


# ─── gleif_ems_match ─────────────────────────────────────────────────────────

def test_gleif_ems_match_empty_rows_returns_zero_candidates() -> None:
    result = OL.gleif_ems_match(entity_rows=[])
    assert result["openLeiGleifEmsMatch"]["candidateCount"] == 0


def test_gleif_ems_match_finds_matching_keyword() -> None:
    rows = [{"lei": "E001", "legal_name": "Tokyo Electronics Corp", "country": "JP"}]
    result = OL.gleif_ems_match(entity_rows=rows, keywords=["electronics"])
    body = result["openLeiGleifEmsMatch"]
    assert body["candidateCount"] == 1
    assert body["candidates"][0]["lei"] == "E001"


def test_gleif_ems_match_filters_by_country() -> None:
    rows = [
        {"lei": "E001", "legal_name": "Electronics Corp", "country": "JP"},
        {"lei": "E002", "legal_name": "Electronics Ltd", "country": "US"},
    ]
    result = OL.gleif_ems_match(entity_rows=rows, countries=["JP"], keywords=["electronics"])
    assert result["openLeiGleifEmsMatch"]["candidateCount"] == 1


def test_gleif_ems_match_no_country_filter() -> None:
    rows = [
        {"lei": "E001", "legal_name": "Electronics Corp", "country": "JP"},
        {"lei": "E002", "legal_name": "Electronics Ltd", "country": "US"},
    ]
    result = OL.gleif_ems_match(entity_rows=rows, keywords=["electronics"])
    assert result["openLeiGleifEmsMatch"]["candidateCount"] == 2


def test_gleif_ems_match_score_increases_with_more_keywords() -> None:
    rows = [{"lei": "E001", "legal_name": "Electronics Manufacturing Technology Corp", "country": "JP"}]
    result = OL.gleif_ems_match(entity_rows=rows, keywords=["electronics", "manufacturing", "technology"])
    candidate = result["openLeiGleifEmsMatch"]["candidates"][0]
    assert len(candidate["matchedKeywords"]) == 3
    assert candidate["score"] > 50


def test_gleif_ems_match_score_capped_at_100() -> None:
    rows = [{"lei": "E001", "legal_name": "electronics manufacturing technology assembly industrial corp", "country": "JP"}]
    result = OL.gleif_ems_match(entity_rows=rows, keywords=["electronics", "manufacturing", "technology", "assembly", "industrial", "extra", "more"])
    candidate = result["openLeiGleifEmsMatch"]["candidates"][0]
    assert candidate["score"] <= 100


def test_gleif_ems_match_case_insensitive() -> None:
    rows = [{"lei": "E001", "legal_name": "ELECTRONICS CORP", "country": "JP"}]
    result = OL.gleif_ems_match(entity_rows=rows, keywords=["electronics"])
    assert result["openLeiGleifEmsMatch"]["candidateCount"] == 1


def test_gleif_ems_match_next_evidence_is_list() -> None:
    rows = [{"lei": "E001", "legal_name": "Manufacturing Co", "country": "JP"}]
    result = OL.gleif_ems_match(entity_rows=rows, keywords=["manufacturing"])
    candidate = result["openLeiGleifEmsMatch"]["candidates"][0]
    assert isinstance(candidate["nextEvidence"], list)


# ─── normalize_ownership_record ──────────────────────────────────────────────

_RR_RECORD = {
    "type": "relationship-records",
    "id": "test-rr-01",
    "attributes": {
        "relationship": {
            "startNode": {"nodeID": "CHILD001", "nodeIDType": "LEI"},
            "endNode":   {"nodeID": "PARENT001", "nodeIDType": "LEI"},
            "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
            "periods": [{"startDate": "2020-01-01", "endDate": None}],
            "percentageDirectlyOwned": 75.0,
            "status": "ACTIVE",
        }
    },
}


def test_normalize_ownership_record_basic() -> None:
    result = OL.normalize_ownership_record(_RR_RECORD)
    assert result is not None
    row, edge = result
    assert row["parent_lei"] == "PARENT001"
    assert row["child_lei"] == "CHILD001"
    assert row["relationship_type"] == "IS_DIRECTLY_CONSOLIDATED_BY"
    assert row["ownership_pct"] == 75.0
    assert row["status"] == "active"


def test_normalize_ownership_record_vertex_id_format() -> None:
    result = OL.normalize_ownership_record(_RR_RECORD)
    assert result is not None
    row, _ = result
    assert "PARENT001--CHILD001" in row["vertex_id"]


def test_normalize_ownership_record_edge_direction() -> None:
    result = OL.normalize_ownership_record(_RR_RECORD)
    assert result is not None
    _, edge = result
    # child → parent direction
    assert "CHILD001" in edge["src_vid"]
    assert "PARENT001" in edge["dst_vid"]


def test_normalize_ownership_record_inactive_status() -> None:
    rec = {
        "attributes": {
            "relationship": {
                "startNode": {"nodeID": "C2", "nodeIDType": "LEI"},
                "endNode":   {"nodeID": "P2", "nodeIDType": "LEI"},
                "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY",
                "periods": [],
                "percentageDirectlyOwned": None,
                "status": "INACTIVE",
            }
        }
    }
    result = OL.normalize_ownership_record(rec)
    assert result is not None
    row, _ = result
    assert row["status"] == "inactive"
    assert row["ownership_pct"] is None


def test_normalize_ownership_record_flat_format() -> None:
    rec = {"parentLei": "FLAT_P", "childLei": "FLAT_C", "ownershipPct": 51.0}
    result = OL.normalize_ownership_record(rec)
    assert result is not None
    row, _ = result
    assert row["parent_lei"] == "FLAT_P"
    assert row["child_lei"] == "FLAT_C"
    assert row["ownership_pct"] == 51.0


def test_normalize_ownership_record_same_lei_skipped() -> None:
    rec = {"parentLei": "SAME001", "childLei": "SAME001"}
    assert OL.normalize_ownership_record(rec) is None


def test_normalize_ownership_record_missing_leis_skipped() -> None:
    assert OL.normalize_ownership_record({}) is None
    assert OL.normalize_ownership_record({"parentLei": "P"}) is None


def test_normalize_ownership_record_required_keys() -> None:
    result = OL.normalize_ownership_record(_RR_RECORD)
    assert result is not None
    row, edge = result
    for key in ("vertex_id", "parent_lei", "child_lei", "relationship_type", "status",
                "created_at", "owner_did", "sensitivity_ord"):
        assert key in row, f"missing key: {key}"
    for key in ("edge_id", "src_vid", "dst_vid", "role"):
        assert key in edge, f"missing edge key: {key}"


# ─── gleif_ownership_ingest (dry_run) ────────────────────────────────────────

def test_gleif_ownership_ingest_dry_run_no_db() -> None:
    result = OL.gleif_ownership_ingest(ownership_rows=[_RR_RECORD], dry_run=True)
    out = result["openLeiOwnershipIngest"]
    assert out["recordsRead"] == 1
    assert out["recordsNormalized"] == 1
    assert out["inserted"] == 0
    assert out["dryRun"] is True


def test_gleif_ownership_ingest_empty_rows() -> None:
    result = OL.gleif_ownership_ingest(ownership_rows=[], dry_run=True)
    out = result["openLeiOwnershipIngest"]
    assert out["recordsRead"] == 0
    assert out["recordsNormalized"] == 0
    assert out["inserted"] == 0


def test_gleif_ownership_ingest_filters_invalid() -> None:
    rows = [_RR_RECORD, {}, {"parentLei": "SAME", "childLei": "SAME"}]
    result = OL.gleif_ownership_ingest(ownership_rows=rows, dry_run=True)
    out = result["openLeiOwnershipIngest"]
    assert out["recordsRead"] == 3
    assert out["recordsNormalized"] == 1


def test_task_gleif_ownership_ingest_from_normalize_output() -> None:
    normalize_output = {"ownershipRows": [_RR_RECORD]}
    result = OL.task_gleif_ownership_ingest(
        openLeiGleifRecordNormalize=normalize_output, dryRun=True
    )
    assert "openLeiOwnershipIngest" in result
    assert result["openLeiOwnershipIngest"]["recordsNormalized"] == 1


def test_task_gleif_ownership_ingest_direct_rows() -> None:
    result = OL.task_gleif_ownership_ingest(ownershipRows=[_RR_RECORD], dryRun=True)
    assert result["openLeiOwnershipIngest"]["recordsNormalized"] == 1
