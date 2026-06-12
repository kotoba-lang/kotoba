"""Pure helper tests for mixed primitives.

Covers pure functions and constants in:
- langgraph_registry: register / get / list_ids
- graph_consumer: _utc_now_iso / _camel_to_snake / _maps_entity_label /
                  _convention_candidates / constants
- maps_building_3d: _now_iso / _stable_rkey / _lat_lng_to_h3_approx /
                    _centroid_of_cell / constants
- shinshi_video: _build_wan_i2v_workflow / _extract_video_b64
- science_knowledge: _NOW / _CPK_COLORS / _ELEMENTS constants
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import langgraph_registry as LR
from kotodama.primitives import graph_consumer as GC
from kotodama.primitives import maps_building_3d as MB3
from kotodama.primitives import shinshi_video as SV
from kotodama.primitives import science_knowledge as SK


# ─── langgraph_registry ───────────────────────────────────────────────────────

def test_lr_register_and_get():
    LR.register("test.graph.v1", object())
    assert LR.get("test.graph.v1") is not None


def test_lr_get_missing_returns_none():
    assert LR.get("nonexistent.graph") is None


def test_lr_list_ids_after_register():
    LR.register("test.list.v2", object())
    ids = LR.list_ids()
    assert "test.list.v2" in ids


def test_lr_list_ids_returns_list():
    assert isinstance(LR.list_ids(), list)


def test_lr_register_overwrites():
    sentinel_a = object()
    sentinel_b = object()
    LR.register("overwrite.test", sentinel_a)
    LR.register("overwrite.test", sentinel_b)
    assert LR.get("overwrite.test") is sentinel_b


def test_lr_register_preserves_graph():
    class FakeGraph:
        def ainvoke(self): ...
    g = FakeGraph()
    LR.register("fake.graph.v3", g)
    assert LR.get("fake.graph.v3") is g


# ─── graph_consumer — _utc_now_iso ───────────────────────────────────────────

def test_gc_utc_now_iso_returns_string():
    assert isinstance(GC._utc_now_iso(), str)


def test_gc_utc_now_iso_ends_with_z():
    assert GC._utc_now_iso().endswith("Z")


def test_gc_utc_now_iso_contains_t():
    assert "T" in GC._utc_now_iso()


# ─── graph_consumer — _camel_to_snake ────────────────────────────────────────

def test_gc_camel_to_snake_single_word():
    assert GC._camel_to_snake("hello") == "hello"


def test_gc_camel_to_snake_basic():
    assert GC._camel_to_snake("helloWorld") == "hello_world"


def test_gc_camel_to_snake_multiple_caps():
    assert GC._camel_to_snake("myEntityType") == "my_entity_type"


def test_gc_camel_to_snake_edge_from_entity():
    assert GC._camel_to_snake("edgeFollows") == "edge_follows"


def test_gc_camel_to_snake_already_snake():
    assert GC._camel_to_snake("already_snake") == "already_snake"


def test_gc_camel_to_snake_empty():
    assert GC._camel_to_snake("") == ""


# ─── graph_consumer — _maps_entity_label ─────────────────────────────────────

def test_gc_maps_entity_label_asset_special():
    result = GC._maps_entity_label("asset")
    assert result == "PhysicalAsset"


def test_gc_maps_entity_label_capitalizes_first():
    result = GC._maps_entity_label("building")
    assert result == "Building"


def test_gc_maps_entity_label_route():
    result = GC._maps_entity_label("route")
    assert result == "Route"


def test_gc_maps_entity_label_unknown_preserves_rest():
    result = GC._maps_entity_label("myEntity")
    assert result == "MyEntity"


# ─── graph_consumer — _convention_candidates ─────────────────────────────────

def test_gc_convention_candidates_non_nsid():
    assert GC._convention_candidates("app.bsky.feed.post") == []


def test_gc_convention_candidates_regular_entity():
    result = GC._convention_candidates("com.etzhayyim.apps.hr.employee")
    assert "vertex_hr_employee" in result


def test_gc_convention_candidates_edge_entity():
    result = GC._convention_candidates("com.etzhayyim.apps.graph.edgeFollows")
    assert any("edge_" in r for r in result)


def test_gc_convention_candidates_maps_vertex():
    result = GC._convention_candidates("com.etzhayyim.apps.maps.building")
    assert "vertex_spatial" in result


def test_gc_convention_candidates_maps_control_plane_excluded():
    result = GC._convention_candidates("com.etzhayyim.apps.maps.mapsSource")
    assert "vertex_spatial" not in result


# ─── graph_consumer — constants ──────────────────────────────────────────────

def test_gc_graph_did_is_string():
    assert isinstance(GC.GRAPH_DID, str)


def test_gc_graph_did_starts_with_did():
    assert GC.GRAPH_DID.startswith("did:")


def test_gc_consume_tick_collection_is_string():
    assert isinstance(GC.CONSUME_TICK_COLLECTION, str)


def test_gc_consume_tick_collection_has_graph():
    assert "graph" in GC.CONSUME_TICK_COLLECTION


def test_gc_default_timeout_is_positive():
    assert GC.DEFAULT_TIMEOUT_SEC > 0


def test_gc_collection_to_table_has_bsky_profile():
    assert "app.bsky.actor.profile" in GC._COLLECTION_TO_TABLE


def test_gc_collection_to_table_has_follow():
    assert "app.bsky.graph.follow" in GC._COLLECTION_TO_TABLE


# ─── maps_building_3d — _now_iso ─────────────────────────────────────────────

def test_mb3_now_iso_returns_string():
    assert isinstance(MB3._now_iso(), str)


def test_mb3_now_iso_ends_with_z():
    assert MB3._now_iso().endswith("Z")


def test_mb3_now_iso_contains_t():
    assert "T" in MB3._now_iso()


# ─── maps_building_3d — _stable_rkey ─────────────────────────────────────────

def test_mb3_stable_rkey_is_deterministic():
    a = MB3._stable_rkey("at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.building/001")
    b = MB3._stable_rkey("at://did:web:maps.etzhayyim.com/com.etzhayyim.apps.maps.building/001")
    assert a == b


def test_mb3_stable_rkey_differs_by_input():
    a = MB3._stable_rkey("vertex-id-A")
    b = MB3._stable_rkey("vertex-id-B")
    assert a != b


def test_mb3_stable_rkey_length_16():
    result = MB3._stable_rkey("any-value")
    assert len(result) == 16


def test_mb3_stable_rkey_hex_chars():
    result = MB3._stable_rkey("some-vertex-id")
    int(result, 16)  # raises ValueError if not hex


# ─── maps_building_3d — _lat_lng_to_h3_approx ───────────────────────────────

def test_mb3_h3_approx_returns_string():
    result = MB3._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert isinstance(result, str)


def test_mb3_h3_approx_starts_with_h3():
    result = MB3._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert result.startswith("h3_")


def test_mb3_h3_approx_contains_res():
    result = MB3._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert "10" in result


def test_mb3_h3_approx_different_coords_differ():
    a = MB3._lat_lng_to_h3_approx(35.0, 139.0, 10)
    b = MB3._lat_lng_to_h3_approx(40.0, 135.0, 10)
    assert a != b


def test_mb3_h3_approx_same_coords_consistent():
    a = MB3._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    b = MB3._lat_lng_to_h3_approx(35.6762, 139.6503, 10)
    assert a == b


# ─── maps_building_3d — _centroid_of_cell ────────────────────────────────────

def test_mb3_centroid_roundtrip_close():
    lat, lng = 35.6762, 139.6503
    cell = MB3._lat_lng_to_h3_approx(lat, lng, 10)
    c_lat, c_lng = MB3._centroid_of_cell(cell)
    assert abs(c_lat - lat) < 0.01
    assert abs(c_lng - lng) < 0.01


def test_mb3_centroid_invalid_key_returns_zeros():
    lat, lng = MB3._centroid_of_cell("invalid")
    assert lat == 0.0 and lng == 0.0


def test_mb3_centroid_returns_tuple():
    cell = MB3._lat_lng_to_h3_approx(0.0, 0.0, 10)
    result = MB3._centroid_of_cell(cell)
    assert isinstance(result, tuple) and len(result) == 2


# ─── maps_building_3d — constants ────────────────────────────────────────────

def test_mb3_default_repo_is_did():
    assert MB3.DEFAULT_REPO.startswith("did:")


def test_mb3_collection_building_3d_has_maps():
    assert "maps" in MB3.COLLECTION_BUILDING_3D


def test_mb3_collection_coverage_has_maps():
    assert "maps" in MB3.COLLECTION_COVERAGE


def test_mb3_m_per_deg_lat_approx():
    assert 100_000 < MB3._M_PER_DEG_LAT < 120_000


def test_mb3_max_cells_default_positive():
    assert MB3._MAX_CELLS_DEFAULT > 0


# ─── shinshi_video — _build_wan_i2v_workflow ─────────────────────────────────

def test_sv_workflow_returns_dict():
    result = SV._build_wan_i2v_workflow("motion", 480, 360, 16, 16)
    assert isinstance(result, dict)


def test_sv_workflow_has_sampler_node():
    result = SV._build_wan_i2v_workflow("test", 480, 360, 16, 16)
    assert any("Sampler" in v.get("class_type", "") for v in result.values())


def test_sv_workflow_has_save_node():
    result = SV._build_wan_i2v_workflow("test", 480, 360, 16, 16)
    assert any("Save" in v.get("class_type", "") for v in result.values())


def test_sv_workflow_width_in_sampler():
    result = SV._build_wan_i2v_workflow("prompt", 640, 480, 24, 24)
    sampler = next(v for v in result.values() if "Sampler" in v.get("class_type", ""))
    assert sampler["inputs"]["width"] == 640


def test_sv_workflow_height_in_sampler():
    result = SV._build_wan_i2v_workflow("prompt", 640, 480, 24, 24)
    sampler = next(v for v in result.values() if "Sampler" in v.get("class_type", ""))
    assert sampler["inputs"]["height"] == 480


def test_sv_workflow_short_length_clamped():
    result = SV._build_wan_i2v_workflow("test", 480, 360, 2, 16)
    sampler = next(v for v in result.values() if "Sampler" in v.get("class_type", ""))
    assert sampler["inputs"]["num_frames"] >= 8


def test_sv_workflow_prompt_in_text_encode():
    result = SV._build_wan_i2v_workflow("cinematic sunset", 480, 360, 16, 16)
    text_nodes = [v for v in result.values() if "TextEncode" in v.get("class_type", "")]
    assert any("cinematic sunset" in str(n["inputs"].get("positive_prompt", "")) for n in text_nodes)


# ─── shinshi_video — _extract_video_b64 ──────────────────────────────────────

def test_sv_extract_video_b64_from_video_key():
    result = SV._extract_video_b64({"video": "abc123=="})
    assert result == "abc123=="


def test_sv_extract_video_b64_from_videos_list():
    result = SV._extract_video_b64({"videos": [{"data": "xyz=="}]})
    assert result == "xyz=="


def test_sv_extract_video_b64_from_videos_string_item():
    result = SV._extract_video_b64({"videos": ["direct_b64"]})
    assert result == "direct_b64"


def test_sv_extract_video_b64_empty_dict():
    assert SV._extract_video_b64({}) == ""


def test_sv_extract_video_b64_non_dict():
    assert SV._extract_video_b64(None) == ""


def test_sv_extract_video_b64_empty_videos_list():
    assert SV._extract_video_b64({"videos": []}) == ""


# ─── science_knowledge — _NOW ────────────────────────────────────────────────

def test_sk_now_returns_string():
    assert isinstance(SK._NOW(), str)


def test_sk_now_ends_with_z():
    assert SK._NOW().endswith("Z")


def test_sk_now_contains_t():
    assert "T" in SK._NOW()


# ─── science_knowledge — _CPK_COLORS ─────────────────────────────────────────

def test_sk_cpk_colors_is_dict():
    assert isinstance(SK._CPK_COLORS, dict)


def test_sk_cpk_colors_has_hydrogen():
    assert "H" in SK._CPK_COLORS


def test_sk_cpk_colors_has_carbon():
    assert "C" in SK._CPK_COLORS


def test_sk_cpk_colors_values_are_rgb_tuples():
    for sym, color in SK._CPK_COLORS.items():
        assert len(color) == 3, f"{sym} color not RGB tuple"
        for channel in color:
            assert 0.0 <= channel <= 1.0, f"{sym} channel out of range"


# ─── science_knowledge — _ELEMENTS ───────────────────────────────────────────

def test_sk_elements_is_list():
    assert isinstance(SK._ELEMENTS, list)


def test_sk_elements_not_empty():
    assert len(SK._ELEMENTS) > 0


def test_sk_elements_have_symbol():
    for elem in SK._ELEMENTS:
        assert "sym" in elem


def test_sk_elements_have_atomic_number():
    for elem in SK._ELEMENTS:
        assert "z" in elem
        assert elem["z"] > 0


def test_sk_elements_hydrogen_is_first():
    assert SK._ELEMENTS[0]["sym"] == "H"


def test_sk_elements_atomic_numbers_ascending():
    zs = [e["z"] for e in SK._ELEMENTS]
    assert zs == sorted(zs)
