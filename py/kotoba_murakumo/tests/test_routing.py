"""Routing decisions — pure function, no HTTP."""

from __future__ import annotations

from pathlib import Path

import pytest

from kotoba_murakumo import gpu
from kotoba_murakumo._internal.routing import resolve
from kotoba_murakumo.exceptions import FleetUnreachable, MurakumoCompatNotImplemented
from kotoba_murakumo.fleet import load


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


@pytest.fixture(scope="module")
def fleet():
    return load(_repo_root() / "50-infra/murakumo/fleet.toml")


def test_none_routes_to_litellm_gateway(fleet) -> None:
    r = resolve(None, "gemma4:e4b", fleet)
    assert r.backend == "litellm-gateway"
    assert r.url == "http://100.113.200.45:4000"
    assert r.kind == "openai-compatible"
    # The judah-hosted LiteLLM gateway requires bearer auth per
    # ADR-2605282400 §"Routing fix" (empirically verified 2026-05-28 —
    # without this the gateway returns 401 Unauthorized).
    assert r.auth_bearer_env == "LITELLM_MASTER_KEY"


def test_any_str_routes_to_litellm_gateway(fleet) -> None:
    r = resolve("any", "gemma4:e4b", fleet)
    assert r.backend == "litellm-gateway"


def test_mac_mini_routes_to_own_node_ollama(fleet) -> None:
    r = resolve(gpu.MacMini(node="benjamin"), "gemma4:e4b-it-qat", fleet)
    assert r.backend == "mac-mini/benjamin"
    assert r.url == "http://100.75.169.8:11434"
    assert r.kind == "ollama-native"


def test_evo_x2_default_prefers_litellm(fleet) -> None:
    r = resolve(gpu.EvoX2(), "llama3.3:70b", fleet)
    assert r.backend == "evo-x2"
    assert r.url == "http://100.113.200.45:4000"
    assert r.auth_bearer_env == "LITELLM_MASTER_KEY"


def test_evo_x2_prefer_ollama(fleet) -> None:
    r = resolve(gpu.EvoX2(prefer="ollama"), "llama3.2:3b", fleet)
    assert r.url == "http://100.75.169.8:11434"
    assert r.kind == "openai-compatible"  # ollama exposes OpenAI-compat


def test_evo_x2_prefer_comfyui(fleet) -> None:
    r = resolve(gpu.EvoX2(prefer="comfyui"), None, fleet)
    assert r.backend == "evo-x2"
    assert r.url == "http://100.75.169.8:8188"
    assert r.kind == "comfyui-native"


def test_modal_string_a100_routes_to_evo_x2(fleet) -> None:
    r = resolve("A100", "llama3.2:3b", fleet)
    assert r.backend == "evo-x2"


def test_webgpu_lands_r2(fleet) -> None:
    with pytest.raises(MurakumoCompatNotImplemented) as ei:
        resolve(gpu.WebGPU(), "any", fleet)
    assert "R2" in str(ei.value)


def test_unknown_node_raises(fleet) -> None:
    with pytest.raises(FleetUnreachable):
        resolve(gpu.MacMini(node="not-a-tribe"), "gemma4:e4b", fleet)
