"""Tests for pure helpers in handlers/gameka_codegen.py:
_biome_for, _camera_for, _input_for, _safe_str, _mechanic_for.
Also covers handlers/gameka_avatar.py: _normalise_biome, _palette_for."""

from __future__ import annotations

import importlib.util as _ilu
import sys
import types as _ty
from pathlib import Path as _P

_ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"

_MOD_CG = "_gameka_codegen"
if _MOD_CG in sys.modules:
    cg = sys.modules[_MOD_CG]
else:
    _spec = _ilu.spec_from_file_location(_MOD_CG, _ROOT / "handlers" / "gameka_codegen.py")
    cg = _ty.ModuleType(_MOD_CG)
    sys.modules[_MOD_CG] = cg
    assert _spec and _spec.loader
    _spec.loader.exec_module(cg)  # type: ignore[union-attr]

_MOD_AV = "_gameka_avatar"
if _MOD_AV in sys.modules:
    av = sys.modules[_MOD_AV]
else:
    _spec2 = _ilu.spec_from_file_location(_MOD_AV, _ROOT / "handlers" / "gameka_avatar.py")
    av = _ty.ModuleType(_MOD_AV)
    sys.modules[_MOD_AV] = av
    assert _spec2 and _spec2.loader
    _spec2.loader.exec_module(av)  # type: ignore[union-attr]


# ─── _biome_for ──────────────────────────────────────────────────────────────

def test_biome_for_default_when_empty() -> None:
    assert cg._biome_for("") == "Plains"


def test_biome_for_default_when_none() -> None:
    assert cg._biome_for(None) == "Plains"  # type: ignore[arg-type]


def test_biome_for_plains_keyword() -> None:
    assert cg._biome_for("an open plains scene") == "Plains"


def test_biome_for_desert_keyword() -> None:
    assert cg._biome_for("a sandy desert") == "Desert"


def test_biome_for_tundra_keyword() -> None:
    assert cg._biome_for("frozen tundra landscape") == "Tundra"


def test_biome_for_quarry_keyword() -> None:
    assert cg._biome_for("deep cave environment") == "Quarry"


def test_biome_for_snow_maps_to_tundra() -> None:
    assert cg._biome_for("snowy snow mountains") == "Tundra"


def test_biome_for_dune_maps_to_desert() -> None:
    assert cg._biome_for("rolling dune fields") == "Desert"


def test_biome_for_case_insensitive() -> None:
    assert cg._biome_for("FOREST scene") == "Plains"


def test_biome_for_no_match_returns_plains() -> None:
    assert cg._biome_for("underwater ocean reef") == "Plains"


# ─── _camera_for ─────────────────────────────────────────────────────────────

def test_camera_for_default_when_empty() -> None:
    assert cg._camera_for("") == "Orbit"


def test_camera_for_default_when_none() -> None:
    assert cg._camera_for(None) == "Orbit"  # type: ignore[arg-type]


def test_camera_for_platformer() -> None:
    assert cg._camera_for("platformer") == "ThirdPerson"


def test_camera_for_puzzle() -> None:
    assert cg._camera_for("puzzle") == "Orbit"


def test_camera_for_shmup() -> None:
    assert cg._camera_for("shmup") == "TopDown"


def test_camera_for_sandbox() -> None:
    assert cg._camera_for("sandbox") == "Fps"


def test_camera_for_case_insensitive() -> None:
    assert cg._camera_for("Platformer") == "ThirdPerson"


def test_camera_for_unknown_genre_defaults() -> None:
    assert cg._camera_for("unknown-genre") == "Orbit"


# ─── _input_for ──────────────────────────────────────────────────────────────

def test_input_for_default_when_empty() -> None:
    assert cg._input_for("") == "PointerOrbit"


def test_input_for_default_when_none() -> None:
    assert cg._input_for(None) == "PointerOrbit"  # type: ignore[arg-type]


def test_input_for_platformer() -> None:
    assert cg._input_for("platformer") == "Wasd"


def test_input_for_runner() -> None:
    assert cg._input_for("runner") == "ArrowsOnly"


def test_input_for_rhythm() -> None:
    assert cg._input_for("rhythm") == "BeatTap"


def test_input_for_tower_defense() -> None:
    assert cg._input_for("tower-defense") == "PointerSelect"


def test_input_for_case_insensitive() -> None:
    assert cg._input_for("SANDBOX") == "WasdMouseLook"


def test_input_for_unknown_defaults() -> None:
    assert cg._input_for("unknown") == "PointerOrbit"


# ─── _safe_str ───────────────────────────────────────────────────────────────

def test_safe_str_plain_text() -> None:
    assert cg._safe_str("hello world") == "hello world"


def test_safe_str_none_returns_empty() -> None:
    assert cg._safe_str(None) == ""


def test_safe_str_escapes_backslash() -> None:
    result = cg._safe_str("a\\b")
    assert "\\\\" in result


def test_safe_str_escapes_double_quote() -> None:
    result = cg._safe_str('say "hi"')
    assert '\\"' in result
    assert '"hi"' not in result


def test_safe_str_newline_replaced_with_space() -> None:
    result = cg._safe_str("line1\nline2")
    assert "\n" not in result
    assert "line1" in result and "line2" in result


def test_safe_str_carriage_return_replaced() -> None:
    result = cg._safe_str("line1\rline2")
    assert "\r" not in result


def test_safe_str_truncates_at_max_len() -> None:
    result = cg._safe_str("a" * 300, max_len=100)
    assert len(result) == 100


def test_safe_str_default_max_len_200() -> None:
    result = cg._safe_str("a" * 300)
    assert len(result) == 200


def test_safe_str_int_input() -> None:
    result = cg._safe_str(42)
    assert result == "42"


def test_safe_str_empty_string() -> None:
    assert cg._safe_str("") == ""


# ─── _mechanic_for ───────────────────────────────────────────────────────────

def test_mechanic_for_empty_dict_returns_default() -> None:
    kind, src = cg._mechanic_for({})
    assert kind == "grid_2048"
    assert isinstance(src, str) and len(src) > 0


def test_mechanic_for_explicit_kind_grid_2048() -> None:
    kind, _ = cg._mechanic_for({"kind": "grid_2048"})
    assert kind == "grid_2048"


def test_mechanic_for_explicit_kind_drop_suika() -> None:
    kind, _ = cg._mechanic_for({"kind": "drop_suika"})
    assert kind == "drop_suika"


def test_mechanic_for_explicit_kind_field_triple() -> None:
    kind, _ = cg._mechanic_for({"kind": "field_triple"})
    assert kind == "field_triple"


def test_mechanic_for_unknown_explicit_kind_falls_through_to_text_scan() -> None:
    kind, _ = cg._mechanic_for({"kind": "nonexistent", "coreVerb": "drop items"})
    assert kind == "drop_suika"


def test_mechanic_for_coreVerb_drop_maps_to_drop_suika() -> None:
    kind, _ = cg._mechanic_for({"coreVerb": "drop items from top"})
    assert kind == "drop_suika"


def test_mechanic_for_description_physics_maps_to_drop_suika() -> None:
    kind, _ = cg._mechanic_for({"description": "physics-based stacking"})
    assert kind == "drop_suika"


def test_mechanic_for_place_keyword_maps_to_field_triple() -> None:
    kind, _ = cg._mechanic_for({"coreVerb": "place tiles on board"})
    assert kind == "field_triple"


def test_mechanic_for_cluster_maps_to_field_triple() -> None:
    kind, _ = cg._mechanic_for({"description": "cluster matching puzzle"})
    assert kind == "field_triple"


def test_mechanic_for_swipe_maps_to_grid_2048() -> None:
    kind, _ = cg._mechanic_for({"coreVerb": "swipe to merge"})
    assert kind == "grid_2048"


def test_mechanic_for_2048_in_description_maps_to_grid() -> None:
    kind, _ = cg._mechanic_for({"description": "like 2048 but with colors"})
    assert kind == "grid_2048"


def test_mechanic_for_returns_non_empty_rust_source() -> None:
    _, src = cg._mechanic_for({"kind": "drop_suika"})
    assert len(src) > 100


# ─── gameka_avatar._normalise_biome ──────────────────────────────────────────

def test_normalise_biome_known_biome() -> None:
    assert av._normalise_biome("plains") == "plains"


def test_normalise_biome_quarry() -> None:
    assert av._normalise_biome("quarry") == "quarry"


def test_normalise_biome_unknown_returns_default() -> None:
    assert av._normalise_biome("ocean") == "default"


def test_normalise_biome_empty_returns_default() -> None:
    assert av._normalise_biome("") == "default"


def test_normalise_biome_strips_non_alpha() -> None:
    result = av._normalise_biome("pla!ins")
    assert result == "plains"


def test_normalise_biome_uppercase() -> None:
    assert av._normalise_biome("TUNDRA") == "tundra"


def test_normalise_biome_none_returns_default() -> None:
    assert av._normalise_biome(None) == "default"  # type: ignore[arg-type]


# ─── gameka_avatar._palette_for ──────────────────────────────────────────────

def test_palette_for_plains_returns_tuple() -> None:
    palette = av._palette_for("plains")
    assert isinstance(palette, tuple) and len(palette) > 0


def test_palette_for_known_biome_differs_from_default() -> None:
    palette = av._palette_for("tundra")
    default = av._palette_for("unknown-biome")
    assert palette != default


def test_palette_for_unknown_returns_default_palette() -> None:
    palette = av._palette_for("underwater")
    assert palette == av._DEFAULT_PALETTE


def test_palette_for_each_entry_is_rgb_triple() -> None:
    for entry in av._palette_for("desert"):
        assert len(entry) == 3
        assert all(0 <= v <= 255 for v in entry)


def test_palette_for_empty_string_returns_default() -> None:
    assert av._palette_for("") == av._DEFAULT_PALETTE


# ─── _parse_json ─────────────────────────────────────────────────────────────

def test_parse_json_dict_passthrough() -> None:
    d = {"key": "value"}
    assert cg._parse_json(d) is d


def test_parse_json_valid_json_string() -> None:
    assert cg._parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_empty_string_returns_empty_dict() -> None:
    assert cg._parse_json("") == {}


def test_parse_json_none_returns_empty_dict() -> None:
    assert cg._parse_json(None) == {}


def test_parse_json_list_json_returns_empty_dict() -> None:
    assert cg._parse_json("[1, 2, 3]") == {}


def test_parse_json_invalid_json_returns_empty_dict() -> None:
    assert cg._parse_json("not json") == {}


def test_parse_json_nested_dict() -> None:
    result = cg._parse_json('{"a": {"b": 2}}')
    assert result == {"a": {"b": 2}}


# ─── gameka_avatar._png_chunk ────────────────────────────────────────────────

import struct as _struct
import zlib as _zlib


def test_png_chunk_length() -> None:
    data = b"hello"
    chunk = av._png_chunk(b"tEXt", data)
    assert len(chunk) == 4 + 4 + len(data) + 4


def test_png_chunk_starts_with_big_endian_data_length() -> None:
    data = b"abc"
    chunk = av._png_chunk(b"tEXt", data)
    length_field = _struct.unpack(">I", chunk[:4])[0]
    assert length_field == len(data)


def test_png_chunk_contains_type_bytes() -> None:
    chunk = av._png_chunk(b"IDAT", b"\x00" * 10)
    assert chunk[4:8] == b"IDAT"


def test_png_chunk_contains_data() -> None:
    payload = b"\x01\x02\x03"
    chunk = av._png_chunk(b"IHDR", payload)
    assert chunk[8:11] == payload


def test_png_chunk_crc32_correct() -> None:
    typ = b"IEND"
    data = b""
    chunk = av._png_chunk(typ, data)
    expected_crc = _zlib.crc32(typ + data) & 0xFFFFFFFF
    actual_crc = _struct.unpack(">I", chunk[-4:])[0]
    assert actual_crc == expected_crc


def test_png_chunk_deterministic() -> None:
    a = av._png_chunk(b"tEXt", b"hello")
    b = av._png_chunk(b"tEXt", b"hello")
    assert a == b


def test_png_chunk_varies_with_data() -> None:
    a = av._png_chunk(b"tEXt", b"hello")
    b = av._png_chunk(b"tEXt", b"world")
    assert a != b


def test_png_chunk_varies_with_type() -> None:
    a = av._png_chunk(b"IDAT", b"data")
    b = av._png_chunk(b"tEXt", b"data")
    assert a != b


def test_png_chunk_empty_data() -> None:
    chunk = av._png_chunk(b"IEND", b"")
    assert len(chunk) == 12
    length_field = _struct.unpack(">I", chunk[:4])[0]
    assert length_field == 0
