"""Pure helper tests for open_lei and hanrei primitives.

Covers pure functions with no DB/HTTP dependencies:
- open_lei: _utc_now / _as_list / _str_list / normalize_lei_record /
             gleif_manifest_plan / gleif_record_normalize / gleif_ems_match /
             GLEIF_DATASETS
- hanrei: _utc_now / _job_vid / _case_vid / _jurisdiction_vid / _court_vid /
           _new_job_id / _OWNER_DID / _JP_COURTS / _JP_SOURCES /
           _EGOV_CATEGORIES
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import open_lei as OL
from kotodama.primitives import hanrei as HR


# ─── open_lei — _utc_now ─────────────────────────────────────────────────────

def test_ol_utc_now_returns_string():
    assert isinstance(OL._utc_now(), str)


def test_ol_utc_now_ends_with_z():
    assert OL._utc_now().endswith("Z")


def test_ol_utc_now_contains_t():
    assert "T" in OL._utc_now()


# ─── open_lei — _as_list ─────────────────────────────────────────────────────

def test_ol_as_list_list_returns_list():
    val = [1, 2, 3]
    assert OL._as_list(val) is val


def test_ol_as_list_non_list_returns_empty():
    assert OL._as_list(None) == []
    assert OL._as_list("string") == []
    assert OL._as_list(42) == []


def test_ol_as_list_empty_list_returns_empty():
    assert OL._as_list([]) == []


# ─── open_lei — _str_list ────────────────────────────────────────────────────

def test_ol_str_list_converts_to_strings():
    result = OL._str_list([1, 2, 3])
    assert result == ["1", "2", "3"]


def test_ol_str_list_filters_falsy():
    result = OL._str_list([1, None, 0, "ok"])
    assert result == ["1", "ok"]


def test_ol_str_list_non_list_returns_empty():
    assert OL._str_list(None) == []
    assert OL._str_list("abc") == []


def test_ol_str_list_empty_list_returns_empty():
    assert OL._str_list([]) == []


# ─── open_lei — normalize_lei_record ─────────────────────────────────────────

def test_ol_normalize_has_required_keys():
    record = {}
    result = OL.normalize_lei_record(record)
    for key in ("vertex_id", "lei", "legal_name", "country", "status", "owner_did"):
        assert key in result


def test_ol_normalize_extracts_lei_from_attributes():
    record = {
        "attributes": {
            "lei": "ABC123",
            "entity": {"legalName": {"name": "Test Corp"}, "legalAddress": {"country": "US"}},
            "registration": {"status": "ISSUED"},
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["lei"] == "ABC123"
    assert result["legal_name"] == "Test Corp"
    assert result["country"] == "US"


def test_ol_normalize_status_issued_is_active():
    record = {
        "attributes": {
            "lei": "X1",
            "entity": {},
            "registration": {"status": "ISSUED"},
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["status"] == "active"


def test_ol_normalize_status_lapsed_for_non_issued():
    record = {
        "attributes": {
            "lei": "X2",
            "entity": {},
            "registration": {"status": "LAPSED"},
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["status"] == "lapsed"


def test_ol_normalize_vertex_id_starts_with_at():
    record = {"attributes": {"lei": "MYWEI"}}
    result = OL.normalize_lei_record(record)
    assert result["vertex_id"].startswith("at://")


# ─── open_lei — gleif_manifest_plan ──────────────────────────────────────────

def test_ol_gleif_manifest_plan_returns_dict():
    result = OL.gleif_manifest_plan()
    assert isinstance(result, dict)


def test_ol_gleif_manifest_plan_has_outer_key():
    result = OL.gleif_manifest_plan()
    assert "openLeiGleifManifestPlan" in result


def test_ol_gleif_manifest_plan_with_date():
    result = OL.gleif_manifest_plan(as_of_date="2026-04-01")
    plan = result["openLeiGleifManifestPlan"]
    assert plan["asOfDate"] == "2026-04-01"


def test_ol_gleif_manifest_plan_has_datasets():
    result = OL.gleif_manifest_plan()
    plan = result["openLeiGleifManifestPlan"]
    assert isinstance(plan["datasets"], list)
    assert len(plan["datasets"]) > 0


def test_ol_gleif_manifest_plan_selected_datasets():
    result = OL.gleif_manifest_plan(datasets=["lei-cdf"])
    plan = result["openLeiGleifManifestPlan"]
    assert len(plan["datasets"]) == 1
    assert plan["datasets"][0]["datasetKind"] == "lei-cdf"


def test_ol_gleif_manifest_plan_unknown_dataset_skipped():
    result = OL.gleif_manifest_plan(datasets=["lei-cdf", "bogus-dataset"])
    plan = result["openLeiGleifManifestPlan"]
    assert len(plan["datasets"]) == 1


def test_ol_gleif_manifest_plan_invalid_mode_defaults_to_delta():
    result = OL.gleif_manifest_plan(mode="bogus")
    plan = result["openLeiGleifManifestPlan"]
    assert plan["mode"] == "delta"


# ─── open_lei — gleif_record_normalize ───────────────────────────────────────

def test_ol_gleif_record_normalize_returns_dict():
    result = OL.gleif_record_normalize()
    assert isinstance(result, dict)


def test_ol_gleif_record_normalize_no_records():
    result = OL.gleif_record_normalize(dataset_kind="lei-cdf", records=None)
    norm = result["openLeiGleifRecordNormalize"]
    assert norm["recordsRead"] == 0
    assert norm["entityRows"] == []


def test_ol_gleif_record_normalize_lei_cdf_creates_entity_rows():
    records = [
        {"attributes": {"lei": "LEI001", "entity": {}, "registration": {"status": "ISSUED"}}}
    ]
    result = OL.gleif_record_normalize(dataset_kind="lei-cdf", records=records)
    norm = result["openLeiGleifRecordNormalize"]
    assert norm["recordsRead"] == 1
    assert len(norm["entityRows"]) == 1


def test_ol_gleif_record_normalize_rr_cdf_no_entity_rows():
    records = [{"some": "data"}]
    result = OL.gleif_record_normalize(dataset_kind="rr-cdf", records=records)
    norm = result["openLeiGleifRecordNormalize"]
    assert norm["entityRows"] == []


# ─── open_lei — gleif_ems_match ──────────────────────────────────────────────

def test_ol_gleif_ems_match_returns_dict():
    result = OL.gleif_ems_match()
    assert isinstance(result, dict)


def test_ol_gleif_ems_match_has_key():
    result = OL.gleif_ems_match()
    assert "openLeiGleifEmsMatch" in result


def test_ol_gleif_ems_match_no_rows_returns_empty_candidates():
    result = OL.gleif_ems_match(entity_rows=None)
    match = result["openLeiGleifEmsMatch"]
    assert match["candidates"] == []


# ─── open_lei — GLEIF_DATASETS ───────────────────────────────────────────────

def test_ol_gleif_datasets_is_dict():
    assert isinstance(OL.GLEIF_DATASETS, dict)


def test_ol_gleif_datasets_has_lei_cdf():
    assert "lei-cdf" in OL.GLEIF_DATASETS


def test_ol_gleif_datasets_has_target_tables():
    for key, val in OL.GLEIF_DATASETS.items():
        assert "targetTables" in val


# ─── hanrei — _utc_now ───────────────────────────────────────────────────────

def test_hr_utc_now_returns_string():
    assert isinstance(HR._utc_now(), str)


def test_hr_utc_now_ends_with_z():
    assert HR._utc_now().endswith("Z")


def test_hr_utc_now_contains_t():
    assert "T" in HR._utc_now()


# ─── hanrei — vid helpers ────────────────────────────────────────────────────

def test_hr_job_vid_starts_with_at():
    result = HR._job_vid("job-001")
    assert result.startswith("at://")


def test_hr_job_vid_contains_job_id():
    result = HR._job_vid("job-abc")
    assert "job-abc" in result


def test_hr_case_vid_starts_with_at():
    result = HR._case_vid("case-001")
    assert result.startswith("at://")


def test_hr_case_vid_contains_rkey():
    result = HR._case_vid("supreme-1973")
    assert "supreme-1973" in result


def test_hr_jurisdiction_vid_starts_with_at():
    result = HR._jurisdiction_vid("JPN")
    assert result.startswith("at://")


def test_hr_jurisdiction_vid_is_deterministic():
    a = HR._jurisdiction_vid("JPN")
    b = HR._jurisdiction_vid("JPN")
    assert a == b


def test_hr_jurisdiction_vid_differs_by_iso3():
    a = HR._jurisdiction_vid("JPN")
    b = HR._jurisdiction_vid("USA")
    assert a != b


def test_hr_court_vid_starts_with_at():
    result = HR._court_vid("supreme")
    assert result.startswith("at://")


def test_hr_court_vid_is_deterministic():
    a = HR._court_vid("supreme")
    b = HR._court_vid("supreme")
    assert a == b


def test_hr_court_vid_differs_by_court():
    a = HR._court_vid("supreme")
    b = HR._court_vid("district")
    assert a != b


# ─── hanrei — _new_job_id ────────────────────────────────────────────────────

def test_hr_new_job_id_returns_string():
    assert isinstance(HR._new_job_id(), str)


def test_hr_new_job_id_is_unique():
    a = HR._new_job_id()
    b = HR._new_job_id()
    assert a != b


def test_hr_new_job_id_len_16():
    result = HR._new_job_id()
    assert len(result) == 16


# ─── hanrei — _OWNER_DID ─────────────────────────────────────────────────────

def test_hr_owner_did_starts_with_did():
    assert HR._OWNER_DID.startswith("did:")


def test_hr_owner_did_contains_hanrei():
    assert "hanrei" in HR._OWNER_DID


# ─── hanrei — _JP_COURTS ─────────────────────────────────────────────────────

def test_hr_jp_courts_is_list():
    assert isinstance(HR._JP_COURTS, list)


def test_hr_jp_courts_not_empty():
    assert len(HR._JP_COURTS) > 0


def test_hr_jp_courts_have_court_id():
    for court in HR._JP_COURTS:
        assert "courtId" in court
        assert isinstance(court["courtId"], str)


def test_hr_jp_courts_have_name():
    for court in HR._JP_COURTS:
        assert "name" in court


def test_hr_jp_courts_contain_supreme():
    court_ids = {c["courtId"] for c in HR._JP_COURTS}
    assert "supreme" in court_ids


# ─── hanrei — _JP_SOURCES ────────────────────────────────────────────────────

def test_hr_jp_sources_is_list():
    assert isinstance(HR._JP_SOURCES, list)


def test_hr_jp_sources_not_empty():
    assert len(HR._JP_SOURCES) > 0


def test_hr_jp_sources_have_source_id():
    for src in HR._JP_SOURCES:
        assert "sourceId" in src


# ─── hanrei — _EGOV_CATEGORIES ───────────────────────────────────────────────

def test_hr_egov_categories_is_list():
    assert isinstance(HR._EGOV_CATEGORIES, list)


def test_hr_egov_categories_not_empty():
    assert len(HR._EGOV_CATEGORIES) > 0


def test_hr_egov_categories_have_id():
    for cat in HR._EGOV_CATEGORIES:
        assert "id" in cat
        assert isinstance(cat["id"], int)


def test_hr_egov_categories_have_name():
    for cat in HR._EGOV_CATEGORIES:
        assert "name" in cat
