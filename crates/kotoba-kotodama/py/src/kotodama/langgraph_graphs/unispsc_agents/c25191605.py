# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191605 — Spacecraft (segment 25).

Bespoke graph logic for spacecraft procurement and configuration management.
This agent handles mission profile validation, telemetry verification, and
environmental envelope verification for aerospace assets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191605"
UNISPSC_TITLE = "Spacecraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Spacecraft
    mission_profile: str
    telemetry_status: str
    environmental_verification: bool
    payload_mass_kg: float


def validate_mission_specs(state: State) -> dict[str, Any]:
    """Analyzes input for spacecraft mission profile and payload requirements."""
    inp = state.get("input") or {}
    profile = inp.get("mission", "unspecified")
    mass = float(inp.get("mass", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_mission_specs -> {profile}"],
        "mission_profile": profile,
        "payload_mass_kg": mass,
    }


def verify_systems(state: State) -> dict[str, Any]:
    """Simulates verification of orbital telemetry and environmental testing."""
    mass = state.get("payload_mass_kg", 0.0)
    # Logic: Heavier payloads require more rigorous environmental verification
    env_ok = mass < 5000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_systems -> telemetry_active:true"],
        "telemetry_status": "linked",
        "environmental_verification": env_ok,
    }


def finalize_asset_manifest(state: State) -> dict[str, Any]:
    """Compiles the final spacecraft specification and readiness report."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission": state.get("mission_profile"),
            "readiness_score": 1.0 if state.get("environmental_verification") else 0.8,
            "telemetry": state.get("telemetry_status"),
            "status": "manifested",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_mission_specs", validate_mission_specs)
_g.add_node("verify_systems", verify_systems)
_g.add_node("finalize_asset_manifest", finalize_asset_manifest)

_g.add_edge(START, "validate_mission_specs")
_g.add_edge("validate_mission_specs", "verify_systems")
_g.add_edge("verify_systems", "finalize_asset_manifest")
_g.add_edge("finalize_asset_manifest", END)

graph = _g.compile()
