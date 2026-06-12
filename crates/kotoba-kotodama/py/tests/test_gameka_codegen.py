"""
Offline unit tests for gameka.codegen.renderKamiApp + the gameka_studio
LangGraph deliberation agent.

Both tests stay offline:
  - codegen tests are pure-function (no LLM, no DB, no network).
  - studio tests stub `kotodama.llm.call_tier_json` so the LangGraph
    state machine runs end-to-end against canned responses.

Pattern mirrors `test_dns_resolve.py` — import leaf modules via importlib
rather than the `kotodama.handlers` / `kotodama.agents` packages,
because their __init__.py eagerly loads sibling modules that may not
have all deps available in the test venv.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
import types
from pathlib import Path as _P

ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"


def _load(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ─── codegen (pure function) ───────────────────────────────────────────


cg = _load("_gameka_codegen", "handlers/gameka_codegen.py")


def test_render_emits_four_files_with_known_paths():
    # P13 adds src/mechanic.rs alongside Cargo.toml + src/lib.rs + README.md.
    out = cg._render_kami_app_sources(
        spec_id="spec1700000000abc123",
        title="Quarry Rune",
        slug="quarry-rune",
        genre="rogue-lite",
        mechanic_json='{"description":"collect runes, escape the quarry"}',
        scene_json='{"description":"quarry biome with rolling fog"}',
    )
    assert set(out.keys()) == {
        "Cargo.toml", "src/lib.rs", "src/mechanic.rs", "README.md",
    }


def test_render_picks_biome_camera_input_from_spec():
    out = cg._render_kami_app_sources(
        spec_id="s",
        title="Tundra Drift",
        slug="tundra-drift",
        genre="runner",
        mechanic_json="{}",
        scene_json='{"description":"snow tundra plain at dusk"}',
    )
    lib = out["src/lib.rs"]
    assert "Biome::Tundra" in lib
    assert "CameraMode::ThirdPerson" in lib
    assert "InputMode::ArrowsOnly" in lib


def test_render_falls_back_to_plains_orbit_pointer_for_unknown_genre():
    out = cg._render_kami_app_sources(
        spec_id="s",
        title="Untyped",
        slug="untyped",
        genre="nonexistent-genre",
        mechanic_json="{}",
        scene_json="{}",
    )
    lib = out["src/lib.rs"]
    assert "Biome::Plains" in lib
    assert "CameraMode::Orbit" in lib
    assert "InputMode::PointerOrbit" in lib


def test_entry_fn_underscores_hyphens():
    assert cg._entry_fn("quarry-rune") == "run_quarry_rune"
    assert cg._entry_fn("game") == "run_game"


def test_slug_normalises_punctuation():
    assert cg._slug("Quarry Rune!") == "quarry-rune"
    assert cg._slug("  WHITESPACE  ") == "whitespace"
    assert cg._slug("") == "game"


def test_render_is_deterministic():
    args = dict(
        spec_id="spec-deterministic",
        title="Test",
        slug="test-game",
        genre="puzzle",
        mechanic_json='{"description":"swap tiles"}',
        scene_json='{"description":"plains"}',
    )
    a = cg._render_kami_app_sources(**args)
    b = cg._render_kami_app_sources(**args)
    assert a == b
    blob_a = cg._canonical_blob(a)
    blob_b = cg._canonical_blob(b)
    assert blob_a == blob_b
    assert cg._cidv1_b32_sha256(blob_a) == cg._cidv1_b32_sha256(blob_b)


# ─── audio palette ──────────────────────────────────────────────────────


def test_audio_default_when_scene_missing_palette():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json="{}", scene_json="{}",
    )
    lib = out["src/lib.rs"]
    assert 'BGM_HINT: &str = "ambient-default"' in lib
    # Default palette covers loaded/click/coin/success
    assert '"loaded"' in lib and '"click"' in lib and '"coin"' in lib


def test_audio_palette_picked_from_scene():
    scene = (
        '{"description":"quarry hall",'
        '"audioPalette":{"bgm":"ambient-quarry-low",'
        '"sfx":["click","success","coin","tick","select","loaded"]}}'
    )
    out = cg._render_kami_app_sources(
        spec_id="s", title="Q", slug="q", genre="puzzle",
        mechanic_json="{}", scene_json=scene,
    )
    lib = out["src/lib.rs"]
    assert 'BGM_HINT: &str = "ambient-quarry-low"' in lib
    for sfx in ["click", "success", "coin", "tick", "select", "loaded"]:
        assert f'"{sfx}"' in lib


def test_audio_sfx_dedupes_and_normalises():
    scene = (
        '{"audioPalette":{"sfx":["Click","CLICK","click ","whoosh!","BAD NAME"]}}'
    )
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json="{}", scene_json=scene,
    )
    lib = out["src/lib.rs"]
    # "Click" / "CLICK" / "click " all collapse to "click"; "whoosh!"
    # → "whoosh"; "BAD NAME" → "badname".
    assert lib.count('"click"') == 1
    assert '"whoosh"' in lib
    assert '"badname"' in lib


def test_audio_sfx_capped_at_12():
    sfx = [f"snd{i}" for i in range(20)]
    scene = '{"audioPalette":{"sfx":' + cg.json.dumps(sfx) + '}}'
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json="{}", scene_json=scene,
    )
    lib = out["src/lib.rs"]
    # Counts are bounded — only 12 of the 20 names show up.
    seen = sum(1 for i in range(20) if f'"snd{i}"' in lib)
    assert seen == 12


# ─── kami-engine bridges in lib.rs ──────────────────────────────────────


def test_lib_rs_declares_kami_bridges():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json="{}", scene_json="{}",
    )
    lib = out["src/lib.rs"]
    # 4 wasm-bindgen externs that mirror the playtest shell window globals.
    for sym in [
        "js_name = __kamiPlay",
        "js_name = __kamiPlayBgm",
        "js_name = __kamiSocialShare",
        "js_name = __kamiSocialFollow",
    ]:
        assert sym in lib, f"missing extern binding: {sym}"
    # Public exports the game logic can call.
    assert "pub fn play_sfx" in lib
    assert "pub fn start_bgm" in lib
    assert "pub fn share_score" in lib
    assert "pub fn follow_creator" in lib
    # Entry fn boots BGM + the loaded SFX so the playtest probe sees
    # the audio bridge end-to-end.
    assert "start_bgm()" in lib
    assert 'play_sfx("loaded")' in lib


def test_cargo_toml_pulls_kami_audio():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json="{}", scene_json="{}",
    )
    cargo = out["Cargo.toml"]
    assert 'kami-audio = { path = "../kami-audio" }' in cargo


# ─── Mechanic templates (P13) ───────────────────────────────────────────


def test_render_emits_mechanic_rs_file():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"grid_2048"}', scene_json="{}",
    )
    assert "src/mechanic.rs" in out
    rs = out["src/mechanic.rs"]
    assert "pub fn mechanic_init" in rs
    assert "pub fn mechanic_swipe" in rs


def test_mechanic_kind_explicit_grid_2048():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"grid_2048"}', scene_json="{}",
    )
    rs = out["src/mechanic.rs"]
    assert "swipe-merge mechanic" in rs
    assert "pub fn mechanic_swipe" in rs
    # Kind constant is also baked into lib.rs.
    assert 'MECHANIC_KIND: &str = "grid_2048"' in out["src/lib.rs"]


def test_mechanic_kind_explicit_drop_suika():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"drop_suika"}', scene_json="{}",
    )
    rs = out["src/mechanic.rs"]
    assert "Suika-style" in rs
    assert "pub fn mechanic_drop_at" in rs
    assert "pub fn mechanic_step" in rs
    assert 'MECHANIC_KIND: &str = "drop_suika"' in out["src/lib.rs"]


def test_mechanic_kind_explicit_field_triple():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"field_triple"}', scene_json="{}",
    )
    rs = out["src/mechanic.rs"]
    assert "place-and-cluster" in rs
    assert "pub fn mechanic_place" in rs
    assert "pub fn mechanic_preview" in rs
    assert 'MECHANIC_KIND: &str = "field_triple"' in out["src/lib.rs"]


def test_mechanic_kind_inferred_from_core_verb_when_unset():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"coreVerb":"drop-and-fuse"}', scene_json="{}",
    )
    assert 'MECHANIC_KIND: &str = "drop_suika"' in out["src/lib.rs"]


def test_mechanic_kind_inferred_from_description():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"description":"place tiles in clusters of three"}',
        scene_json="{}",
    )
    assert 'MECHANIC_KIND: &str = "field_triple"' in out["src/lib.rs"]


def test_mechanic_kind_default_grid_2048_for_unknown():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"chess"}',  # not a known mechanic
        scene_json="{}",
    )
    # Falls through to keyword scan (none), then to default.
    assert 'MECHANIC_KIND: &str = "grid_2048"' in out["src/lib.rs"]


def test_mechanic_seed_is_deterministic_per_spec_id():
    out1 = cg._render_kami_app_sources(
        spec_id="spec-merge-grid-2048", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"grid_2048"}', scene_json="{}",
    )
    out2 = cg._render_kami_app_sources(
        spec_id="spec-merge-grid-2048", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"grid_2048"}', scene_json="{}",
    )
    out3 = cg._render_kami_app_sources(
        spec_id="spec-merge-drop-suika", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"drop_suika"}', scene_json="{}",
    )
    # Same spec_id → identical lib.rs (incl. seed); different spec_id
    # → different seed → different lib.rs.
    assert out1["src/lib.rs"] == out2["src/lib.rs"]
    assert out1["src/lib.rs"] != out3["src/lib.rs"]


def test_lib_rs_invokes_mechanic_init():
    out = cg._render_kami_app_sources(
        spec_id="s", title="T", slug="t", genre="puzzle",
        mechanic_json='{"kind":"grid_2048"}', scene_json="{}",
    )
    lib = out["src/lib.rs"]
    assert "pub mod mechanic;" in lib
    assert "mechanic::mechanic_init(" in lib


def test_three_seed_specs_produce_three_distinct_mechanics():
    out_grid = cg._render_kami_app_sources(
        spec_id="spec-merge-grid-2048", title="T", slug="grid-merge-quarry", genre="puzzle",
        mechanic_json='{"kind":"grid_2048"}',
        scene_json='{"description":"quarry biome"}',
    )
    out_drop = cg._render_kami_app_sources(
        spec_id="spec-merge-drop-suika", title="T", slug="drop-merge-tundra", genre="puzzle",
        mechanic_json='{"kind":"drop_suika"}',
        scene_json='{"description":"tundra biome"}',
    )
    out_field = cg._render_kami_app_sources(
        spec_id="spec-merge-field-triple", title="T", slug="field-merge-plains", genre="puzzle",
        mechanic_json='{"kind":"field_triple"}',
        scene_json='{"description":"plains biome"}',
    )
    # All three render distinct mechanic.rs files.
    assert out_grid["src/mechanic.rs"] != out_drop["src/mechanic.rs"]
    assert out_drop["src/mechanic.rs"] != out_field["src/mechanic.rs"]
    assert out_grid["src/mechanic.rs"] != out_field["src/mechanic.rs"]
    # ...and distinct CIDs (composition with different lib.rs + scene
    # descriptions adds further variance, but mechanic alone is enough).
    blob_g = cg._canonical_blob(out_grid)
    blob_d = cg._canonical_blob(out_drop)
    blob_f = cg._canonical_blob(out_field)
    assert len({
        cg._cidv1_b32_sha256(blob_g),
        cg._cidv1_b32_sha256(blob_d),
        cg._cidv1_b32_sha256(blob_f),
    }) == 3


def test_cidv1_shape():
    cid = cg._cidv1_b32_sha256(b"hello")
    assert cid.startswith("b")
    assert len(cid) >= 50
    assert all(c in "abcdefghijklmnopqrstuvwxyz234567" for c in cid[1:])


def test_template_escapes_quotes_in_user_text():
    out = cg._render_kami_app_sources(
        spec_id="s",
        title='Game "X"',
        slug="g",
        genre="puzzle",
        mechanic_json='{"description":"verb \\"jump\\""}',
        scene_json="{}",
    )
    # Renders without throwing; embedded quotes are escaped, not raw.
    assert '"jump"' not in out["src/lib.rs"]


# ─── codegen task wrapper ──────────────────────────────────────────────


def test_task_returns_failed_on_missing_input():
    import asyncio
    out = asyncio.run(
        cg.task_gameka_codegen_render_kami_app(specId="", title="", slug="")
    )
    assert out["buildStatus"] == "failed"


def test_task_returns_sources_ready_on_valid_input():
    import asyncio
    out = asyncio.run(
        cg.task_gameka_codegen_render_kami_app(
            specId="spec1",
            title="Plains Hop",
            slug="plains-hop",
            genre="platformer",
            mechanicJson='{"description":"hop between plates"}',
            sceneJson='{"description":"plains biome"}',
        )
    )
    assert out["buildStatus"] == "sources_ready"
    assert out["entryFn"] == "run_plains_hop"
    # P13: src/mechanic.rs is the 4th file alongside Cargo.toml +
    # src/lib.rs + README.md.
    assert out["fileCount"] == 4
    assert out["wasmSize"] > 0
    assert out["wasmCid"].startswith("b")


# ─── LangGraph deliberation (stubbed LLM) ───────────────────────────────


def _install_llm_stub(planner_payload: dict, critic_payload: dict) -> list:
    """Stub kotodama.llm so the gameka_studio graph runs offline."""
    calls: list[dict] = []
    stub = types.ModuleType("kotodama.llm")

    def call_tier_json(tier, system="", user="", max_tokens=0, temperature=0.0):
        calls.append({"tier": tier, "system": system[:60], "user": user[:60]})
        # First call planner (low temp threshold suffices), second critic.
        # Distinguish by which system prompt fragment is used.
        if "score game specs" in system:
            return {"ok": True, "data": critic_payload, "model": "stub-critic"}
        return {"ok": True, "data": planner_payload, "model": "stub-planner"}

    stub.call_tier_json = call_tier_json
    sys.modules["kotodama.llm"] = stub
    # Also make `kotodama` package available
    if "kotodama" not in sys.modules:
        sys.modules["kotodama"] = types.ModuleType("kotodama")
    sys.modules["kotodama"].llm = stub  # type: ignore[attr-defined]
    return calls


def _try_load_studio():
    """LangGraph is an optional test dep. Skip if not installed."""
    try:
        import langgraph  # noqa: F401
    except ImportError:  # pragma: no cover
        import pytest

        pytest.skip("langgraph not installed in test venv")
    return _load("_gameka_studio", "agents/gameka_studio.py")


def test_studio_finalizes_on_high_score_first_iteration():
    planner = {"candidates": [
        {"title": "A", "slug": "a", "genre": "puzzle", "mechanic": "m", "scene": "plains", "budgetUsd": 100},
        {"title": "B", "slug": "b", "genre": "shmup",  "mechanic": "m", "scene": "tundra", "budgetUsd": 100},
        {"title": "C", "slug": "c", "genre": "runner", "mechanic": "m", "scene": "desert", "budgetUsd": 100},
    ]}
    critic = {"selected": 0, "score": 0.91, "rationale": "tight loop", "perCandidate": [
        {"score": 0.91, "reason": "tight"},
        {"score": 0.6, "reason": "ok"},
        {"score": 0.5, "reason": "ok"},
    ]}
    _install_llm_stub(planner, critic)
    studio = _try_load_studio()
    import asyncio
    out = asyncio.run(
        studio.task_agent_gameka_studio(brief="cozy plains game", maxIterations=3, scoreThreshold=0.8)
    )
    assert out["score"] >= 0.9
    assert out["iterations"] == 1
    assert out["title"] == "A"
    assert out["slug"] == "a"
    assert out["specId"].startswith("spec")


def test_studio_loops_until_threshold_then_finalizes():
    planner = {"candidates": [
        {"title": "X", "slug": "x", "genre": "puzzle", "mechanic": "m", "scene": "plains", "budgetUsd": 100},
    ]}
    # Low score every iteration → graph should loop up to maxIterations.
    critic = {"selected": 0, "score": 0.2, "rationale": "weak", "perCandidate": [
        {"score": 0.2, "reason": "weak"},
    ]}
    _install_llm_stub(planner, critic)
    studio = _try_load_studio()
    import asyncio
    out = asyncio.run(
        studio.task_agent_gameka_studio(brief="anything", maxIterations=2, scoreThreshold=0.8)
    )
    # Capped at maxIterations; finalizer still emits a usable spec row.
    assert out["iterations"] <= 2
    assert out["specId"].startswith("spec")
    assert out["score"] == 0.2


def test_studio_rejects_empty_brief_without_llm_call():
    calls = _install_llm_stub({"candidates": []}, {"selected": 0, "score": 0})
    studio = _try_load_studio()
    import asyncio
    out = asyncio.run(
        studio.task_agent_gameka_studio(brief="")
    )
    assert out["specId"] == ""
    assert out["rationale"] == "missing brief"
    assert calls == []
