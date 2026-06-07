"""fleet.toml loader smoke test.

Uses the canonical fleet.toml at ``50-infra/murakumo/fleet.toml`` so we catch
schema drift in the SSoT, not just a synthetic fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kotoba_murakumo.exceptions import FleetUnreachable
from kotoba_murakumo.fleet import load


def _repo_root() -> Path:
    # tests/ → kotoba_murakumo/ → py/ → kotoba/ → 40-engine/ → repo root
    return Path(__file__).resolve().parents[5]


def test_load_canonical_fleet() -> None:
    fleet = load(_repo_root() / "50-infra/murakumo/fleet.toml")

    assert fleet.name == "etzhayyim-murakumo"

    # 10 tribes documented in CLAUDE.md (Status row + fleet.toml). The minimum
    # we require is that judah is present (LiteLLM gateway lives here).
    assert "judah" in fleet.nodes
    judah = fleet.node("judah")
    assert judah.ip_lan == "192.168.1.17"

    # EVO-X2 endpoints declared by the SSoT.
    litellm_ep = fleet.endpoint("evo-x2", "litellm")
    assert litellm_ep.url == "http://192.168.1.70:4000"
    assert litellm_ep.master_key_env == "EVO_X2_LITELLM_KEY"

    ollama_ep = fleet.endpoint("evo-x2", "ollama")
    assert ollama_ep.url == "http://192.168.1.70:11434"

    # Gateway URL is judah :4000 per CLAUDE.md.
    assert fleet.litellm_gateway_url() == "http://192.168.1.17:4000"


def test_missing_fleet_raises() -> None:
    with pytest.raises(FleetUnreachable):
        load("/nonexistent/fleet.toml")
