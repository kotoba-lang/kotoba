"""Pure helper tests for maps_sentinel, telecom_npn, and telecom_ntn primitives.

Covers pure functions with no DB/HTTP dependencies:
- maps_sentinel: _now_iso / _now_ms / _new_rkey / _build_datetime_range /
                 _parse_aoi / DEFAULT_REPO / COLLECTION_SCENE /
                 _VALID_ANALYSIS_TYPES / _RUNPOD_MAX_POLLS /
                 _BOOTSTRAP_AOIS / ELEMENT84_STAC
- telecom_npn: _now_iso / _hash_id / _new_id / _join / _join_vids /
               _require / _caller / TELECOM_DID / DEPLOYMENT_KINDS /
               ACCESS_KINDS / SLA_TIERS / PROSE_COMM_KINDS / DEVICE_CLASSES
- telecom_ntn: _now_iso / _new_id / _join / _join_vids / _require /
               TELECOM_DID / ORBIT_CLASSES / SERVICE_MODES / ISL_KINDS /
               EPH_FORMATS / HANDOVER_KINDS / CONSTELLATION_KINDS
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps_sentinel as MS
from kotodama.primitives import telecom_npn as NPN
from kotodama.primitives import telecom_ntn as NTN


# ─── maps_sentinel — _now_iso ────────────────────────────────────────────────

def test_ms_now_iso_returns_string():
    assert isinstance(MS._now_iso(), str)


def test_ms_now_iso_ends_with_z():
    assert MS._now_iso().endswith("Z")


def test_ms_now_iso_contains_t():
    assert "T" in MS._now_iso()


# ─── maps_sentinel — _now_ms ─────────────────────────────────────────────────

def test_ms_now_ms_returns_int():
    assert isinstance(MS._now_ms(), int)


def test_ms_now_ms_positive():
    assert MS._now_ms() > 0


# ─── maps_sentinel — _new_rkey ───────────────────────────────────────────────

def test_ms_new_rkey_starts_with_prefix():
    result = MS._new_rkey("scene")
    assert result.startswith("scene-")


def test_ms_new_rkey_unique():
    a = MS._new_rkey("scene")
    b = MS._new_rkey("scene")
    assert a != b


def test_ms_new_rkey_returns_string():
    assert isinstance(MS._new_rkey("analysis"), str)


# ─── maps_sentinel — _build_datetime_range ───────────────────────────────────

def test_ms_build_datetime_range_returns_string():
    result = MS._build_datetime_range(7)
    assert isinstance(result, str)


def test_ms_build_datetime_range_contains_slash():
    result = MS._build_datetime_range(7)
    assert "/" in result


def test_ms_build_datetime_range_both_ends_z():
    result = MS._build_datetime_range(7)
    start, end = result.split("/")
    assert start.endswith("Z")
    assert end.endswith("Z")


def test_ms_build_datetime_range_clamps_to_365():
    result = MS._build_datetime_range(1000)
    assert isinstance(result, str)
    assert "/" in result


def test_ms_build_datetime_range_min_1_day():
    result = MS._build_datetime_range(0)
    assert isinstance(result, str)
    assert "/" in result


# ─── maps_sentinel — _parse_aoi ──────────────────────────────────────────────

def test_ms_parse_aoi_valid():
    spec = {"name": "Tokyo", "bbox": [139.0, 35.0, 140.0, 36.0]}
    result = MS._parse_aoi(spec)
    assert result["name"] == "Tokyo"
    assert result["bbox"] == [139.0, 35.0, 140.0, 36.0]


def test_ms_parse_aoi_non_dict_raises():
    with pytest.raises(ValueError, match="dict"):
        MS._parse_aoi("not-a-dict")


def test_ms_parse_aoi_missing_bbox_raises():
    with pytest.raises(ValueError, match="bbox"):
        MS._parse_aoi({"name": "X"})


def test_ms_parse_aoi_wrong_bbox_length_raises():
    with pytest.raises(ValueError, match="bbox"):
        MS._parse_aoi({"bbox": [1.0, 2.0, 3.0]})


def test_ms_parse_aoi_bad_longitude_raises():
    with pytest.raises(ValueError, match="longitude"):
        MS._parse_aoi({"bbox": [140.0, 35.0, 139.0, 36.0]})


def test_ms_parse_aoi_bad_latitude_raises():
    with pytest.raises(ValueError, match="latitude"):
        MS._parse_aoi({"bbox": [139.0, 36.0, 140.0, 35.0]})


def test_ms_parse_aoi_converts_floats():
    spec = {"bbox": ["139.0", "35.0", "140.0", "36.0"]}
    result = MS._parse_aoi(spec)
    assert all(isinstance(v, float) for v in result["bbox"])


def test_ms_parse_aoi_default_name_empty():
    spec = {"bbox": [139.0, 35.0, 140.0, 36.0]}
    result = MS._parse_aoi(spec)
    assert result["name"] == ""


# ─── maps_sentinel — constants ───────────────────────────────────────────────

def test_ms_default_repo_starts_with_did():
    assert MS.DEFAULT_REPO.startswith("did:")


def test_ms_collection_scene_is_nsid():
    assert "com.etzhayyim.apps.maps" in MS.COLLECTION_SCENE


def test_ms_collection_analysis_is_nsid():
    assert "com.etzhayyim.apps.maps" in MS.COLLECTION_ANALYSIS


def test_ms_valid_analysis_types_is_set():
    assert isinstance(MS._VALID_ANALYSIS_TYPES, set)


def test_ms_valid_analysis_types_not_empty():
    assert len(MS._VALID_ANALYSIS_TYPES) > 0


def test_ms_runpod_max_polls_is_positive_int():
    assert isinstance(MS._RUNPOD_MAX_POLLS, int)
    assert MS._RUNPOD_MAX_POLLS > 0


def test_ms_bootstrap_aois_is_list():
    assert isinstance(MS._BOOTSTRAP_AOIS, list)


def test_ms_bootstrap_aois_not_empty():
    assert len(MS._BOOTSTRAP_AOIS) > 0


def test_ms_element84_stac_is_url():
    assert MS.ELEMENT84_STAC.startswith("https://")


def test_ms_analysis_models_is_dict():
    assert isinstance(MS._ANALYSIS_MODELS, dict)


# ─── telecom_npn — _now_iso ──────────────────────────────────────────────────

def test_npn_now_iso_returns_string():
    assert isinstance(NPN._now_iso(), str)


def test_npn_now_iso_contains_t():
    assert "T" in NPN._now_iso()


# ─── telecom_npn — _hash_id ──────────────────────────────────────────────────

def test_npn_hash_id_none_returns_none():
    assert NPN._hash_id(None) is None


def test_npn_hash_id_empty_returns_none():
    assert NPN._hash_id("") is None


def test_npn_hash_id_adds_sha256_prefix():
    result = NPN._hash_id("supi-001")
    assert result is not None
    assert result.startswith("sha256:")


def test_npn_hash_id_deterministic():
    a = NPN._hash_id("supi-001")
    b = NPN._hash_id("supi-001")
    assert a == b


# ─── telecom_npn — _new_id ───────────────────────────────────────────────────

def test_npn_new_id_with_parts_deterministic():
    a = NPN._new_id("snpn", "plmn-001", "nid-001")
    b = NPN._new_id("snpn", "plmn-001", "nid-001")
    assert a == b


def test_npn_new_id_starts_with_prefix():
    result = NPN._new_id("device", "id-1")
    assert result.startswith("device_")


def test_npn_new_id_without_parts_unique():
    a = NPN._new_id("snpn")
    b = NPN._new_id("snpn")
    assert a != b


# ─── telecom_npn — _join ─────────────────────────────────────────────────────

def test_npn_join_none_returns_none():
    assert NPN._join(None) is None


def test_npn_join_plain_string():
    assert NPN._join("snpn_isolated") == "snpn_isolated"


def test_npn_join_list_joins():
    result = NPN._join(["bronze", "gold"])
    assert result == "bronze,gold"


def test_npn_join_empty_list_returns_none():
    assert NPN._join([]) is None


# ─── telecom_npn — _join_vids ────────────────────────────────────────────────

def test_npn_join_vids_none_returns_none():
    assert NPN._join_vids(None, "snpn") is None


def test_npn_join_vids_non_list_returns_none():
    assert NPN._join_vids("not-list", "snpn") is None


def test_npn_join_vids_empty_list_returns_none():
    assert NPN._join_vids([], "snpn") is None


def test_npn_join_vids_list_returns_string():
    result = NPN._join_vids(["key1", "key2"], "snpn")
    assert result is not None
    assert "key1" in result


# ─── telecom_npn — _require ──────────────────────────────────────────────────

def test_npn_require_present_does_not_raise():
    NPN._require({"snpnId": "s1", "deploymentKind": "snpn_isolated"}, ["snpnId", "deploymentKind"])


def test_npn_require_missing_raises():
    with pytest.raises(ValueError):
        NPN._require({"snpnId": "s1"}, ["snpnId", "deploymentKind"])


# ─── telecom_npn — _caller ───────────────────────────────────────────────────

def test_npn_caller_uses_caller_did():
    result = NPN._caller({"callerDid": "did:web:npn.etzhayyim.com"})
    assert result == "did:web:npn.etzhayyim.com"


def test_npn_caller_falls_back_to_telecom_did():
    result = NPN._caller({})
    assert result == NPN.TELECOM_DID


# ─── telecom_npn — constants ─────────────────────────────────────────────────

def test_npn_telecom_did_starts_with_did():
    assert NPN.TELECOM_DID.startswith("did:")


def test_npn_deployment_kinds_is_set():
    assert isinstance(NPN.DEPLOYMENT_KINDS, set)


def test_npn_deployment_kinds_contains_snpn():
    assert "snpn_isolated" in NPN.DEPLOYMENT_KINDS


def test_npn_access_kinds_is_set():
    assert isinstance(NPN.ACCESS_KINDS, set)


def test_npn_sla_tiers_is_set():
    assert isinstance(NPN.SLA_TIERS, set)


def test_npn_sla_tiers_contains_gold():
    assert "gold" in NPN.SLA_TIERS


def test_npn_prose_comm_kinds_is_set():
    assert isinstance(NPN.PROSE_COMM_KINDS, set)


def test_npn_device_classes_is_set():
    assert isinstance(NPN.DEVICE_CLASSES, set)


def test_npn_device_classes_contains_smartphone():
    assert "smartphone" in NPN.DEVICE_CLASSES


def test_npn_gpsi_kinds_is_set():
    assert isinstance(NPN.GPSI_KINDS, set)


# ─── telecom_ntn — _now_iso ──────────────────────────────────────────────────

def test_ntn_now_iso_returns_string():
    assert isinstance(NTN._now_iso(), str)


def test_ntn_now_iso_contains_t():
    assert "T" in NTN._now_iso()


# ─── telecom_ntn — _new_id ───────────────────────────────────────────────────

def test_ntn_new_id_with_parts_deterministic():
    a = NTN._new_id("sat", "leo-001", "gs-1")
    b = NTN._new_id("sat", "leo-001", "gs-1")
    assert a == b


def test_ntn_new_id_starts_with_prefix():
    result = NTN._new_id("contact", "sat-1")
    assert result.startswith("contact_")


def test_ntn_new_id_without_parts_unique():
    a = NTN._new_id("sat")
    b = NTN._new_id("sat")
    assert a != b


# ─── telecom_ntn — _join ─────────────────────────────────────────────────────

def test_ntn_join_none_returns_none():
    assert NTN._join(None) is None


def test_ntn_join_plain_string():
    assert NTN._join("leo") == "leo"


def test_ntn_join_list_joins():
    result = NTN._join(["leo", "meo"])
    assert result == "leo,meo"


def test_ntn_join_empty_list_returns_none():
    assert NTN._join([]) is None


# ─── telecom_ntn — _join_vids ────────────────────────────────────────────────

def test_ntn_join_vids_none_returns_none():
    assert NTN._join_vids(None, "sat") is None


def test_ntn_join_vids_non_list_returns_none():
    assert NTN._join_vids("not-list", "sat") is None


def test_ntn_join_vids_empty_list_returns_none():
    assert NTN._join_vids([], "sat") is None


def test_ntn_join_vids_list_returns_string():
    result = NTN._join_vids(["key1", "key2"], "sat")
    assert result is not None
    assert "key1" in result


# ─── telecom_ntn — _require ──────────────────────────────────────────────────

def test_ntn_require_present_does_not_raise():
    NTN._require({"satId": "s1", "orbitClass": "leo"}, ["satId", "orbitClass"])


def test_ntn_require_missing_raises():
    with pytest.raises(ValueError):
        NTN._require({"satId": "s1"}, ["satId", "orbitClass"])


# ─── telecom_ntn — constants ─────────────────────────────────────────────────

def test_ntn_telecom_did_starts_with_did():
    assert NTN.TELECOM_DID.startswith("did:")


def test_ntn_orbit_classes_is_set():
    assert isinstance(NTN.ORBIT_CLASSES, set)


def test_ntn_orbit_classes_contains_leo():
    assert "leo" in NTN.ORBIT_CLASSES


def test_ntn_service_modes_is_set():
    assert isinstance(NTN.SERVICE_MODES, set)


def test_ntn_isl_kinds_is_set():
    assert isinstance(NTN.ISL_KINDS, set)


def test_ntn_eph_formats_is_set():
    assert isinstance(NTN.EPH_FORMATS, set)


def test_ntn_eph_formats_contains_tle():
    assert "tle" in NTN.EPH_FORMATS


def test_ntn_handover_kinds_is_set():
    assert isinstance(NTN.HANDOVER_KINDS, set)


def test_ntn_constellation_kinds_is_set():
    assert isinstance(NTN.CONSTELLATION_KINDS, set)


def test_ntn_settlement_modes_is_set():
    assert isinstance(NTN.SETTLEMENT_MODES, set)


def test_ntn_station_kinds_is_set():
    assert isinstance(NTN.STATION_KINDS, set)
