"""Tests for gameka_codegen pure helpers not yet covered:
_normalise_sfx_name, _audio_from_scene."""

from __future__ import annotations

import sys
from pathlib import Path as _P

_ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"
_MOD = "_gameka_codegen"
if _MOD in sys.modules:
    cg = sys.modules[_MOD]
else:
    import importlib.util as _ilu, types as _ty
    _spec = _ilu.spec_from_file_location(_MOD, _ROOT / "handlers" / "gameka_codegen.py")
    cg = _ty.ModuleType(_MOD)
    sys.modules[_MOD] = cg
    assert _spec and _spec.loader
    _spec.loader.exec_module(cg)  # type: ignore[union-attr]


# ─── _normalise_sfx_name ─────────────────────────────────────────────────────

def test_normalise_sfx_plain_lowercase() -> None:
    assert cg._normalise_sfx_name("jump") == "jump"


def test_normalise_sfx_uppercased_becomes_lower() -> None:
    assert cg._normalise_sfx_name("JUMP") == "jump"


def test_normalise_sfx_strips_spaces() -> None:
    assert cg._normalise_sfx_name("jump shot") == "jumpshot"


def test_normalise_sfx_keeps_hyphens() -> None:
    assert cg._normalise_sfx_name("coin-pickup") == "coin-pickup"


def test_normalise_sfx_keeps_underscores() -> None:
    assert cg._normalise_sfx_name("coin_pickup") == "coin_pickup"


def test_normalise_sfx_strips_special_chars() -> None:
    result = cg._normalise_sfx_name("jump!")
    assert "!" not in result


def test_normalise_sfx_truncates_at_32() -> None:
    result = cg._normalise_sfx_name("a" * 50)
    assert len(result) <= 32


def test_normalise_sfx_none_returns_empty() -> None:
    assert cg._normalise_sfx_name(None) == ""


def test_normalise_sfx_empty_returns_empty() -> None:
    assert cg._normalise_sfx_name("") == ""


def test_normalise_sfx_numbers_preserved() -> None:
    assert cg._normalise_sfx_name("sfx2024") == "sfx2024"


# ─── _audio_from_scene ───────────────────────────────────────────────────────

def test_audio_from_scene_empty_dict_uses_defaults() -> None:
    bgm, sfx = cg._audio_from_scene({})
    assert isinstance(bgm, str) and len(bgm) > 0
    assert isinstance(sfx, list) and len(sfx) > 0


def test_audio_from_scene_none_uses_defaults() -> None:
    bgm, sfx = cg._audio_from_scene(None)
    assert isinstance(bgm, str)
    assert isinstance(sfx, list)


def test_audio_from_scene_custom_bgm() -> None:
    scene = {"audioPalette": {"bgm": "forest-ambient"}}
    bgm, _ = cg._audio_from_scene(scene)
    assert bgm == "forest-ambient"


def test_audio_from_scene_custom_sfx() -> None:
    scene = {"audioPalette": {"sfx": ["jump", "collect", "die"]}}
    _, sfx = cg._audio_from_scene(scene)
    assert "jump" in sfx
    assert "collect" in sfx


def test_audio_from_scene_deduplicates_sfx() -> None:
    scene = {"audioPalette": {"sfx": ["jump", "jump", "collect"]}}
    _, sfx = cg._audio_from_scene(scene)
    assert sfx.count("jump") == 1


def test_audio_from_scene_sfx_capped_at_12() -> None:
    names = [f"sfx{i}" for i in range(20)]
    scene = {"audioPalette": {"sfx": names}}
    _, sfx = cg._audio_from_scene(scene)
    assert len(sfx) <= 12


def test_audio_from_scene_invalid_sfx_list_uses_defaults() -> None:
    scene = {"audioPalette": {"sfx": "not-a-list"}}
    _, sfx = cg._audio_from_scene(scene)
    assert isinstance(sfx, list) and len(sfx) > 0


def test_audio_from_scene_empty_sfx_uses_defaults() -> None:
    scene = {"audioPalette": {"sfx": []}}
    _, sfx = cg._audio_from_scene(scene)
    assert len(sfx) > 0


def test_audio_from_scene_bgm_is_string() -> None:
    _, _ = cg._audio_from_scene({})
    bgm, _ = cg._audio_from_scene({})
    assert isinstance(bgm, str)


def test_audio_from_scene_filters_empty_sfx_names() -> None:
    scene = {"audioPalette": {"sfx": ["", "valid", ""]}}
    _, sfx = cg._audio_from_scene(scene)
    assert "" not in sfx
    assert "valid" in sfx
