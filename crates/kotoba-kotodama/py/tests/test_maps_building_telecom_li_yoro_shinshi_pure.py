"""Pure helper tests for maps_building_3d, telecom_li, yoro_social, and
shinshi_video primitives.

Covers pure functions with no DB/HTTP dependencies:
- maps_building_3d: _now_iso / _new_rkey / _stable_rkey /
                    _lat_lng_to_h3_approx / _centroid_of_cell /
                    DEFAULT_REPO / COLLECTION_BUILDING_3D
- telecom_li: _now_iso / _hash_id / _new_id / _require / _caller /
              TELECOM_DID / LI_SENSITIVITY / WARRANT_KINDS /
              INTERCEPT_SCOPES / IDENTIFIER_KINDS
- yoro_social: utc_now_iso / _display_actor / build_social_post_record /
               DEFAULT_REPO / DEFAULT_COLLECTION / DEFAULT_PREFIX
- shinshi_video: _build_wan_i2v_workflow / _extract_video_b64 /
                 _SHINSHI_DID / _VIDEO_RENDER_TIMEOUT_SEC
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps_building_3d as MB
from kotodama.primitives import telecom_li as LI
from kotodama.primitives import yoro_social as YS
from kotodama.primitives import shinshi_video as SV


# ─── maps_building_3d — _now_iso ─────────────────────────────────────────────

def test_mb_now_iso_returns_string():
    assert isinstance(MB._now_iso(), str)


def test_mb_now_iso_ends_with_z():
    assert MB._now_iso().endswith("Z")


def test_mb_now_iso_contains_t():
    assert "T" in MB._now_iso()


# ─── maps_building_3d — _new_rkey ────────────────────────────────────────────

def test_mb_new_rkey_starts_with_prefix():
    result = MB._new_rkey("bld-ingest")
    assert result.startswith("bld-ingest-")


def test_mb_new_rkey_is_unique():
    a = MB._new_rkey("x")
    b = MB._new_rkey("x")
    assert a != b


def test_mb_new_rkey_returns_string():
    assert isinstance(MB._new_rkey("test"), str)


# ─── maps_building_3d — _stable_rkey ─────────────────────────────────────────

def test_mb_stable_rkey_is_deterministic():
    a = MB._stable_rkey("at://did:web:maps.etzhayyim.com/building/001")
    b = MB._stable_rkey("at://did:web:maps.etzhayyim.com/building/001")
    assert a == b


def test_mb_stable_rkey_differs_by_input():
    a = MB._stable_rkey("vertex-001")
    b = MB._stable_rkey("vertex-002")
    assert a != b


def test_mb_stable_rkey_returns_string():
    result = MB._stable_rkey("any-vertex-id")
    assert isinstance(result, str)
    assert len(result) == 16


# ─── maps_building_3d — _lat_lng_to_h3_approx ────────────────────────────────

def test_mb_lat_lng_to_h3_approx_returns_string():
    result = MB._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert isinstance(result, str)


def test_mb_lat_lng_to_h3_approx_starts_with_h3():
    result = MB._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert result.startswith("h3_")


def test_mb_lat_lng_to_h3_approx_contains_res():
    result = MB._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert "_10_" in result


def test_mb_lat_lng_to_h3_approx_is_deterministic():
    a = MB._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    b = MB._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert a == b


def test_mb_lat_lng_to_h3_approx_differs_by_location():
    a = MB._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    b = MB._lat_lng_to_h3_approx(34.6937, 135.5023, 10)  # Osaka
    assert a != b


# ─── maps_building_3d — _centroid_of_cell ────────────────────────────────────

def test_mb_centroid_of_cell_returns_tuple():
    cell = MB._lat_lng_to_h3_approx(35.0, 139.0, 10)
    result = MB._centroid_of_cell(cell)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_mb_centroid_of_cell_invalid_returns_zeros():
    result = MB._centroid_of_cell("not_valid")
    assert result == (0.0, 0.0)


def test_mb_centroid_of_cell_empty_returns_zeros():
    result = MB._centroid_of_cell("")
    assert result == (0.0, 0.0)


def test_mb_centroid_of_cell_approx_correct():
    cell = MB._lat_lng_to_h3_approx(35.0, 139.0, 10)
    lat, lng = MB._centroid_of_cell(cell)
    # centroid should be near the original coordinates
    assert abs(lat - 35.0) < 0.01
    assert abs(lng - 139.0) < 0.01


# ─── maps_building_3d — constants ────────────────────────────────────────────

def test_mb_default_repo_starts_with_did():
    assert MB.DEFAULT_REPO.startswith("did:")


def test_mb_collection_building_3d_is_nsid():
    assert "com.etzhayyim.apps.maps" in MB.COLLECTION_BUILDING_3D


# ─── telecom_li — _now_iso ───────────────────────────────────────────────────

def test_li_now_iso_returns_string():
    assert isinstance(LI._now_iso(), str)


def test_li_now_iso_contains_t():
    assert "T" in LI._now_iso()


# ─── telecom_li — _hash_id ───────────────────────────────────────────────────

def test_li_hash_id_none_returns_none():
    assert LI._hash_id(None) is None


def test_li_hash_id_empty_returns_none():
    assert LI._hash_id("") is None


def test_li_hash_id_whitespace_returns_none():
    assert LI._hash_id("   ") is None


def test_li_hash_id_adds_sha256_prefix():
    result = LI._hash_id("test-msisdn")
    assert result is not None
    assert result.startswith("sha256:")


def test_li_hash_id_is_deterministic():
    a = LI._hash_id("msisdn-001")
    b = LI._hash_id("msisdn-001")
    assert a == b


def test_li_hash_id_differs_by_value():
    a = LI._hash_id("msisdn-001")
    b = LI._hash_id("msisdn-002")
    assert a != b


def test_li_hash_id_int_input():
    result = LI._hash_id(12345)
    assert result is not None
    assert result.startswith("sha256:")


# ─── telecom_li — _new_id ────────────────────────────────────────────────────

def test_li_new_id_with_parts_deterministic():
    a = LI._new_id("warrant", "court-001", "target-x")
    b = LI._new_id("warrant", "court-001", "target-x")
    assert a == b


def test_li_new_id_starts_with_prefix():
    result = LI._new_id("iri", "ev1")
    assert result.startswith("iri_")


def test_li_new_id_without_parts_unique():
    a = LI._new_id("warrant")
    b = LI._new_id("warrant")
    assert a != b


# ─── telecom_li — _require ───────────────────────────────────────────────────

def test_li_require_all_present_no_raise():
    LI._require({"warrantId": "w1", "targetId": "t1"}, ["warrantId", "targetId"])


def test_li_require_missing_raises():
    with pytest.raises(ValueError):
        LI._require({"warrantId": "w1"}, ["warrantId", "targetId"])


def test_li_require_none_value_raises():
    with pytest.raises(ValueError):
        LI._require({"warrantId": None}, ["warrantId"])


# ─── telecom_li — _caller ────────────────────────────────────────────────────

def test_li_caller_uses_caller_did_when_set():
    result = LI._caller({"callerDid": "did:web:regulator.etzhayyim.com"})
    assert result == "did:web:regulator.etzhayyim.com"


def test_li_caller_falls_back_to_telecom_did():
    result = LI._caller({})
    assert result == LI.TELECOM_DID


# ─── telecom_li — constants ──────────────────────────────────────────────────

def test_li_telecom_did_starts_with_did():
    assert LI.TELECOM_DID.startswith("did:")


def test_li_sensitivity_is_int():
    assert isinstance(LI.LI_SENSITIVITY, int)


def test_li_warrant_kinds_is_set():
    assert isinstance(LI.WARRANT_KINDS, set)


def test_li_warrant_kinds_contains_court_order():
    assert "court_order" in LI.WARRANT_KINDS


def test_li_intercept_scopes_is_set():
    assert isinstance(LI.INTERCEPT_SCOPES, set)


def test_li_identifier_kinds_is_set():
    assert isinstance(LI.IDENTIFIER_KINDS, set)


def test_li_identifier_kinds_contains_msisdn():
    assert "msisdn" in LI.IDENTIFIER_KINDS


def test_li_cc_kinds_is_set():
    assert isinstance(LI.CC_KINDS, set)


def test_li_record_kinds_is_set():
    assert isinstance(LI.RECORD_KINDS, set)


# ─── yoro_social — utc_now_iso ───────────────────────────────────────────────

def test_ys_utc_now_iso_returns_string():
    assert isinstance(YS.utc_now_iso(), str)


def test_ys_utc_now_iso_ends_with_z():
    assert YS.utc_now_iso().endswith("Z")


def test_ys_utc_now_iso_contains_t():
    assert "T" in YS.utc_now_iso()


# ─── yoro_social — _display_actor ────────────────────────────────────────────

def test_ys_display_actor_strips_did_web_prefix():
    result = YS._display_actor("did:web:yoro.etzhayyim.com")
    assert result == "yoro.etzhayyim.com"


def test_ys_display_actor_uses_handle_when_provided():
    result = YS._display_actor("did:web:yoro.etzhayyim.com", "yoro-chan")
    assert result == "yoro-chan"


def test_ys_display_actor_empty_falls_back_to_friend():
    result = YS._display_actor("", "")
    assert result == "friend"


def test_ys_display_actor_plain_did_returns_as_is():
    result = YS._display_actor("did:plc:abc123")
    assert result == "did:plc:abc123"


# ─── yoro_social — build_social_post_record ──────────────────────────────────

def test_ys_build_social_post_record_returns_dict():
    result = YS.build_social_post_record(text="test post")
    assert isinstance(result, dict)


def test_ys_build_social_post_record_has_uri():
    result = YS.build_social_post_record(text="hello")
    assert "uri" in result
    assert result["uri"].startswith("at://")


def test_ys_build_social_post_record_has_value_json():
    result = YS.build_social_post_record(text="hello")
    assert "value_json" in result
    import json
    parsed = json.loads(result["value_json"])
    assert parsed["text"] == "hello"


def test_ys_build_social_post_record_custom_repo():
    result = YS.build_social_post_record(repo="did:web:custom.etzhayyim.com", text="t")
    assert "did:web:custom.etzhayyim.com" in result["uri"]


def test_ys_build_social_post_record_has_required_keys():
    result = YS.build_social_post_record(text="x")
    for key in ("uri", "cid", "collection", "rkey", "repo", "value_json", "indexed_at"):
        assert key in result


def test_ys_build_social_post_record_default_collection():
    result = YS.build_social_post_record(text="x")
    assert result["collection"] == "app.bsky.feed.post"


# ─── yoro_social — constants ─────────────────────────────────────────────────

def test_ys_default_repo_starts_with_did():
    assert YS.DEFAULT_REPO.startswith("did:")


def test_ys_default_collection_is_bsky():
    assert "bsky" in YS.DEFAULT_COLLECTION


def test_ys_default_prefix_is_string():
    assert isinstance(YS.DEFAULT_PREFIX, str)
    assert len(YS.DEFAULT_PREFIX) > 0


# ─── shinshi_video — _build_wan_i2v_workflow ─────────────────────────────────

def test_sv_build_workflow_returns_dict():
    result = SV._build_wan_i2v_workflow("a robot dances", 512, 512, 24, 8)
    assert isinstance(result, dict)


def test_sv_build_workflow_has_nodes():
    result = SV._build_wan_i2v_workflow("test", 512, 512, 24, 8)
    assert len(result) >= 3


def test_sv_build_workflow_contains_prompt():
    result = SV._build_wan_i2v_workflow("my custom prompt", 512, 512, 24, 8)
    # prompt appears in text encode node
    found = any(
        "my custom prompt" in str(node.get("inputs", {}).get("positive_prompt", ""))
        for node in result.values()
        if isinstance(node, dict)
    )
    assert found


def test_sv_build_workflow_respects_dimensions():
    result = SV._build_wan_i2v_workflow("test", 640, 480, 24, 8)
    # width and height should appear in sampler node
    found = any(
        node.get("inputs", {}).get("width") == 640
        for node in result.values()
        if isinstance(node, dict)
    )
    assert found


def test_sv_build_workflow_empty_prompt_uses_default():
    result = SV._build_wan_i2v_workflow("", 512, 512, 24, 8)
    found = any(
        "cinematic" in str(node.get("inputs", {}).get("positive_prompt", ""))
        for node in result.values()
        if isinstance(node, dict)
    )
    assert found


# ─── shinshi_video — _extract_video_b64 ──────────────────────────────────────

def test_sv_extract_video_b64_non_dict_returns_empty():
    assert SV._extract_video_b64("not a dict") == ""


def test_sv_extract_video_b64_none_returns_empty():
    assert SV._extract_video_b64(None) == ""


def test_sv_extract_video_b64_video_key():
    result = SV._extract_video_b64({"video": "base64encodeddata"})
    assert result == "base64encodeddata"


def test_sv_extract_video_b64_videos_list():
    result = SV._extract_video_b64({"videos": ["first_video", "second_video"]})
    assert result == "first_video"


def test_sv_extract_video_b64_empty_dict_returns_empty():
    assert SV._extract_video_b64({}) == ""


def test_sv_extract_video_b64_empty_videos_list_returns_empty():
    assert SV._extract_video_b64({"videos": []}) == ""


# ─── shinshi_video — constants ───────────────────────────────────────────────

def test_sv_shinshi_did_starts_with_did():
    assert SV._SHINSHI_DID.startswith("did:")


def test_sv_shinshi_did_contains_shinshi():
    assert "shinshi" in SV._SHINSHI_DID or "sh1n5h1x" in SV._SHINSHI_DID


def test_sv_video_render_timeout_sec_is_float():
    assert isinstance(SV._VIDEO_RENDER_TIMEOUT_SEC, float)


def test_sv_video_render_timeout_sec_positive():
    assert SV._VIDEO_RENDER_TIMEOUT_SEC > 0
