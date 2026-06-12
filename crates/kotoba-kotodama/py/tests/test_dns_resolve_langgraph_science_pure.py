"""Pure helper tests for dns_resolve handler, langgraph_registry primitive, and
science_knowledge primitive.

Covers pure functions with no DB/HTTP/LLM dependencies:
- dns_resolve: _answer_strings / _ALLOWED_RTYPES / _DOH_URL
- langgraph_registry: register / get / list_ids / _REGISTRY
- science_knowledge: _vid / _edge_id / _OWNER_DID / _ELEMENTS /
                     _CPK_COLORS / _VEGETATION_RENDER_PROFILES
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf() decorators work without the runtime dep.
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load_handler(name: str) -> types.ModuleType:
    """Load a handler module by file path (bypasses handlers/__init__)."""
    mod_key = f"_handler_{name}"
    if mod_key in sys.modules:
        return sys.modules[mod_key]
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(mod_key, src)
    assert spec is not None and spec.loader is not None
    mod = types.ModuleType(mod_key)
    sys.modules[mod_key] = mod
    try:
        from kotodama import registry as _reg  # noqa: PLC0415
        to_del = [
            k for k, v in _reg._HANDLERS.items()
            if getattr(getattr(v, "fn", None), "__code__", None)
            and str(src) in v.fn.__code__.co_filename
        ]
        for k in to_del:
            del _reg._HANDLERS[k]
    except Exception:
        pass
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


DR = _load_handler("dns_resolve")

from kotodama.primitives import langgraph_registry as LR
from kotodama.primitives import science_knowledge as SK


# ─── dns_resolve — _answer_strings ───────────────────────────────────────────

def test_dr_answer_strings_status_0_returns_data():
    body = {
        "Status": 0,
        "Answer": [
            {"data": "93.184.216.34", "type": 1},
            {"data": "2606:2800::1", "type": 28},
        ],
    }
    result = DR._answer_strings(body)
    assert result == ["93.184.216.34", "2606:2800::1"]


def test_dr_answer_strings_nonzero_status_returns_empty():
    body = {"Status": 3, "Answer": [{"data": "foo"}]}
    result = DR._answer_strings(body)
    assert result == []


def test_dr_answer_strings_none_returns_empty():
    assert DR._answer_strings(None) == []


def test_dr_answer_strings_empty_dict_returns_empty():
    assert DR._answer_strings({}) == []


def test_dr_answer_strings_no_answer_key_returns_empty():
    body = {"Status": 0}
    result = DR._answer_strings(body)
    assert result == []


def test_dr_answer_strings_empty_answer_list():
    body = {"Status": 0, "Answer": []}
    result = DR._answer_strings(body)
    assert result == []


def test_dr_answer_strings_filters_non_string_data():
    body = {
        "Status": 0,
        "Answer": [
            {"data": "1.2.3.4"},
            {"data": None},
            {"data": 42},
            {},
        ],
    }
    result = DR._answer_strings(body)
    assert result == ["1.2.3.4"]


def test_dr_answer_strings_returns_list():
    result = DR._answer_strings({"Status": 0, "Answer": [{"data": "a"}]})
    assert isinstance(result, list)


# ─── dns_resolve — constants ──────────────────────────────────────────────────

def test_dr_allowed_rtypes_is_frozenset():
    assert isinstance(DR._ALLOWED_RTYPES, frozenset)


def test_dr_allowed_rtypes_contains_a():
    assert "A" in DR._ALLOWED_RTYPES


def test_dr_allowed_rtypes_contains_mx():
    assert "MX" in DR._ALLOWED_RTYPES


def test_dr_allowed_rtypes_contains_txt():
    assert "TXT" in DR._ALLOWED_RTYPES


def test_dr_allowed_rtypes_not_empty():
    assert len(DR._ALLOWED_RTYPES) >= 5


def test_dr_doh_url_is_string():
    assert isinstance(DR._DOH_URL, str)


def test_dr_doh_url_starts_with_https():
    assert DR._DOH_URL.startswith("https://")


# ─── langgraph_registry — register / get / list_ids ──────────────────────────

def _reset_registry():
    LR._REGISTRY.clear()


def test_lr_get_unregistered_returns_none():
    _reset_registry()
    assert LR.get("nonexistent.graph.id") is None


def test_lr_register_then_get():
    _reset_registry()
    sentinel = object()
    LR.register("test.graph.v1", sentinel)
    assert LR.get("test.graph.v1") is sentinel


def test_lr_list_ids_empty_when_empty():
    _reset_registry()
    assert LR.list_ids() == []


def test_lr_list_ids_returns_registered():
    _reset_registry()
    LR.register("alpha.v1", object())
    LR.register("beta.v2", object())
    ids = LR.list_ids()
    assert "alpha.v1" in ids
    assert "beta.v2" in ids


def test_lr_register_overwrites():
    _reset_registry()
    LR.register("my.graph", "first")
    LR.register("my.graph", "second")
    assert LR.get("my.graph") == "second"


def test_lr_list_ids_returns_list():
    _reset_registry()
    assert isinstance(LR.list_ids(), list)


def test_lr_registry_is_dict():
    assert isinstance(LR._REGISTRY, dict)


# ─── science_knowledge — _vid ─────────────────────────────────────────────────

def test_sk_vid_starts_with_at():
    result = SK._vid("science", "element", "H")
    assert result.startswith("at://")


def test_sk_vid_contains_actor():
    result = SK._vid("science", "element", "H")
    assert "science" in result


def test_sk_vid_contains_collection():
    result = SK._vid("science", "element", "H")
    assert "element" in result


def test_sk_vid_contains_rkey():
    result = SK._vid("science", "element", "He-001")
    assert "He-001" in result


def test_sk_vid_returns_string():
    assert isinstance(SK._vid("a", "b", "c"), str)


# ─── science_knowledge — _edge_id ────────────────────────────────────────────

def test_sk_edge_id_returns_string():
    result = SK._edge_id("src", "dst", "rel")
    assert isinstance(result, str)


def test_sk_edge_id_is_deterministic():
    a = SK._edge_id("p", "q", "r")
    b = SK._edge_id("p", "q", "r")
    assert a == b


def test_sk_edge_id_differs_by_parts():
    a = SK._edge_id("src1", "dst", "rel")
    b = SK._edge_id("src2", "dst", "rel")
    assert a != b


def test_sk_edge_id_is_hex():
    result = SK._edge_id("x", "y")
    int(result, 16)


def test_sk_edge_id_len_24():
    result = SK._edge_id("x", "y", "z")
    assert len(result) == 24


# ─── science_knowledge — _OWNER_DID ──────────────────────────────────────────

def test_sk_owner_did_starts_with_did():
    assert SK._OWNER_DID.startswith("did:")


def test_sk_owner_did_contains_science():
    assert "science" in SK._OWNER_DID


# ─── science_knowledge — _ELEMENTS ───────────────────────────────────────────

def test_sk_elements_is_list():
    assert isinstance(SK._ELEMENTS, list)


def test_sk_elements_not_empty():
    assert len(SK._ELEMENTS) > 0


def test_sk_elements_have_sym():
    for el in SK._ELEMENTS:
        assert "sym" in el
        assert isinstance(el["sym"], str)


def test_sk_elements_have_z():
    for el in SK._ELEMENTS:
        assert "z" in el
        assert isinstance(el["z"], int)


def test_sk_elements_have_mass():
    for el in SK._ELEMENTS:
        assert "mass" in el


def test_sk_elements_first_is_hydrogen():
    assert SK._ELEMENTS[0]["sym"] == "H"


def test_sk_elements_second_is_helium():
    assert SK._ELEMENTS[1]["sym"] == "He"


# ─── science_knowledge — _CPK_COLORS ─────────────────────────────────────────

def test_sk_cpk_colors_is_dict():
    assert isinstance(SK._CPK_COLORS, dict)


def test_sk_cpk_colors_has_hydrogen():
    assert "H" in SK._CPK_COLORS


def test_sk_cpk_colors_has_oxygen():
    assert "O" in SK._CPK_COLORS


def test_sk_cpk_colors_values_are_tuples():
    for key, val in SK._CPK_COLORS.items():
        assert isinstance(val, tuple)
        assert len(val) == 3


def test_sk_cpk_colors_values_in_range():
    for key, (r, g, b) in SK._CPK_COLORS.items():
        assert 0.0 <= r <= 1.0
        assert 0.0 <= g <= 1.0
        assert 0.0 <= b <= 1.0


# ─── science_knowledge — _VEGETATION_RENDER_PROFILES ─────────────────────────

def test_sk_vegetation_profiles_is_list():
    assert isinstance(SK._VEGETATION_RENDER_PROFILES, list)


def test_sk_vegetation_profiles_not_empty():
    assert len(SK._VEGETATION_RENDER_PROFILES) > 0


def test_sk_vegetation_profiles_have_common_name():
    for profile in SK._VEGETATION_RENDER_PROFILES:
        assert "commonName" in profile
        assert isinstance(profile["commonName"], str)


def test_sk_vegetation_profiles_have_height_range():
    for profile in SK._VEGETATION_RENDER_PROFILES:
        assert "heightRange" in profile
        assert len(profile["heightRange"]) == 2


def test_sk_vegetation_profiles_contain_grass():
    names = {p["commonName"] for p in SK._VEGETATION_RENDER_PROFILES}
    assert "grass" in names


def test_sk_vegetation_profiles_contain_cactus():
    names = {p["commonName"] for p in SK._VEGETATION_RENDER_PROFILES}
    assert "cactus" in names
