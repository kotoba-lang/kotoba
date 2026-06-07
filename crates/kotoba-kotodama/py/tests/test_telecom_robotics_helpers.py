"""Tests for pure helper functions in telecom.py and robotics.py."""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import date

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import telecom as TC
from kotodama.primitives import robotics as RB


# ─── telecom: _hash_id ───────────────────────────────────────────────────────

def test_hash_id_returns_sha256_prefix() -> None:
    result = TC._hash_id("test-value")
    assert result is not None
    assert result.startswith("sha256:")


def test_hash_id_none_returns_none() -> None:
    assert TC._hash_id(None) is None


def test_hash_id_empty_string_returns_none() -> None:
    assert TC._hash_id("") is None
    assert TC._hash_id("   ") is None


def test_hash_id_deterministic() -> None:
    a = TC._hash_id("msisdn:+1234567890")
    b = TC._hash_id("msisdn:+1234567890")
    assert a == b


def test_hash_id_varies_with_value() -> None:
    a = TC._hash_id("a")
    b = TC._hash_id("b")
    assert a != b


def test_hash_id_hex_length() -> None:
    result = TC._hash_id("value")
    # "sha256:" (7) + 64 hex chars
    assert len(result) == 71


# ─── telecom: _new_id ────────────────────────────────────────────────────────

def test_new_id_with_parts_starts_with_prefix() -> None:
    result = TC._new_id("sub", "part1", "part2")
    assert result.startswith("sub_")


def test_new_id_with_parts_deterministic() -> None:
    a = TC._new_id("sub", "part1", "part2")
    b = TC._new_id("sub", "part1", "part2")
    assert a == b


def test_new_id_with_parts_varies_by_parts() -> None:
    a = TC._new_id("sub", "x")
    b = TC._new_id("sub", "y")
    assert a != b


def test_new_id_without_parts_has_prefix() -> None:
    result = TC._new_id("rand")
    assert result.startswith("rand_")


# ─── telecom: _parse_date ────────────────────────────────────────────────────

def test_parse_date_from_iso_string() -> None:
    result = TC._parse_date("2026-01-15", "start_date")
    assert isinstance(result, date)
    assert result.year == 2026
    assert result.month == 1


def test_parse_date_from_date_object() -> None:
    d = date(2026, 3, 10)
    result = TC._parse_date(d, "field")
    assert result == d


def test_parse_date_extra_time_stripped() -> None:
    result = TC._parse_date("2026-06-01T12:00:00Z", "field")
    assert result.year == 2026
    assert result.month == 6
    assert result.day == 1


def test_parse_date_empty_raises() -> None:
    try:
        TC._parse_date("", "field")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_date_none_raises() -> None:
    try:
        TC._parse_date(None, "field")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ─── telecom: _require ───────────────────────────────────────────────────────

def test_require_passes_with_all_fields() -> None:
    TC._require({"a": "val", "b": "val2"}, ["a", "b"])


def test_require_raises_on_missing() -> None:
    try:
        TC._require({"a": "val"}, ["a", "b"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "b" in str(e)


def test_require_raises_on_empty_string() -> None:
    try:
        TC._require({"a": ""}, ["a"])
        assert False, "expected ValueError"
    except ValueError:
        pass


# ─── telecom: vertex id helpers ──────────────────────────────────────────────

def test_vid_subscriber_shape() -> None:
    vid = TC._vid_subscriber("sub-001")
    assert "at://did:web:telecom.etzhayyim.com" in vid
    assert "com.etzhayyim.apps.telecom.subscriber" in vid
    assert "sub-001" in vid


def test_vid_sim_shape() -> None:
    vid = TC._vid_sim("sim-abc")
    assert "com.etzhayyim.apps.telecom.sim" in vid


def test_vid_service_shape() -> None:
    vid = TC._vid_service("svc-xyz")
    assert "com.etzhayyim.apps.telecom.service" in vid


# ─── telecom: _caller and _audit ─────────────────────────────────────────────

def test_caller_uses_caller_did() -> None:
    result = TC._caller({"callerDid": "did:web:test.etzhayyim.com"})
    assert result == "did:web:test.etzhayyim.com"


def test_caller_default_when_missing() -> None:
    result = TC._caller({})
    assert result  # non-empty default


def test_audit_has_required_fields() -> None:
    result = TC._audit({"callerDid": "did:web:test.etzhayyim.com"})
    assert "created_at" in result
    assert "sensitivity_ord" in result
    assert "org_id" in result


# ─── robotics: _list_str ─────────────────────────────────────────────────────

def test_list_str_converts_items() -> None:
    result = RB._list_str([1, "two", 3.0])
    assert result == ["1", "two", "3.0"]


def test_list_str_filters_falsy() -> None:
    result = RB._list_str(["a", None, "", "b"])
    assert "a" in result and "b" in result
    assert "" not in result
    assert None not in result


def test_list_str_non_list_returns_empty() -> None:
    assert RB._list_str(None) == []
    assert RB._list_str("string") == []


# ─── robotics: _selected_forms ───────────────────────────────────────────────

def test_selected_forms_empty_returns_all() -> None:
    result = RB._selected_forms([])
    assert result == RB.PROCESS_FORMS


def test_selected_forms_none_returns_all() -> None:
    result = RB._selected_forms(None)
    assert result == RB.PROCESS_FORMS


def test_selected_forms_filters_by_process() -> None:
    if not RB.PROCESS_FORMS:
        return
    first_process = RB.PROCESS_FORMS[0]["process"]
    result = RB._selected_forms([first_process])
    assert all(f["process"] == first_process for f in result)


# ─── robotics: _dependency_projection ────────────────────────────────────────

def test_dependency_projection_has_required_keys() -> None:
    result = RB._dependency_projection([])
    assert "dependencies" in result
    assert "missingPrerequisites" in result


def test_dependency_projection_empty_processes() -> None:
    result = RB._dependency_projection([])
    assert isinstance(result["dependencies"], list)
    assert isinstance(result["missingPrerequisites"], list)


# ─── robotics: telecom network coverage ─────────────────────────────────────

def test_robotics_telecom_coverage_contains_satellite_and_gaps() -> None:
    result = RB.robotics_telecom_coverage(media=["satellite-ntn", "bluetooth-ble"])
    coverage = result["roboticsTelecomCoverage"]
    media = {entry["medium"] for entry in coverage["media"]}
    assert "satellite-ntn" in media
    assert "bluetooth-ble" in media
    assert any(gap["medium"] == "bluetooth-ble" for gap in coverage["coverageGaps"])


def test_robotics_network_deployment_plan_blocks_neutron() -> None:
    result = RB.robotics_network_deployment_plan(media=["neutron-communication"])
    plan = result["roboticsNetworkDeploymentPlan"]
    assert plan["status"] == "blocked"
    assert plan["missions"][0]["status"] == "blocked"


def test_robotics_network_deployment_plan_bluetooth_has_schema() -> None:
    result = RB.robotics_network_deployment_plan(media=["bluetooth-ble"])
    plan = result["roboticsNetworkDeploymentPlan"]
    assert plan["status"] == "review"
    assert "vertex_telecom_bluetooth_device" in plan["missions"][0]["telecomSchemas"]


def test_robotics_network_deployment_plan_ran_is_review() -> None:
    result = RB.robotics_network_deployment_plan(media=["cellular-ran"], site_id="site-001")
    plan = result["roboticsNetworkDeploymentPlan"]
    assert plan["siteId"] == "site-001"
    assert plan["status"] == "review"
    assert plan["missions"][0]["medium"] == "cellular-ran"


# ─── robotics: robotics_transport_plan ───────────────────────────────────────

def test_robotics_transport_plan_default() -> None:
    result = RB.robotics_transport_plan()
    assert isinstance(result, dict)
    assert result  # non-empty


def test_robotics_transport_plan_custom_asset() -> None:
    result = RB.robotics_transport_plan(asset_kind="forklift")
    assert isinstance(result, dict)


def test_robotics_transport_plan_custom_route() -> None:
    result = RB.robotics_transport_plan(
        origin="Loading dock",
        destination="Warehouse"
    )
    assert isinstance(result, dict)
