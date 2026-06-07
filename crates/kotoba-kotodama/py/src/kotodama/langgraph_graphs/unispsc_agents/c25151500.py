# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25151500 — Spacecraft (segment 25).

Bespoke logic for spacecraft mission planning and state management.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25151500"
UNISPSC_TITLE = "Spacecraft"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25151500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Spacecraft
    orbit_parameters: dict[str, Any]
    payload_manifest: list[str]
    telemetry_status: str
    launch_configuration: str


def validate_manifest(state: State) -> dict[str, Any]:
    """Validates the spacecraft payload manifest and launch configuration."""
    inp = state.get("input") or {}
    manifest = inp.get("payload", ["Standard Scientific Package"])
    launch_cfg = inp.get("launch_cfg", "Heavy Lift Vehicle")

    return {
        "log": [f"{UNISPSC_CODE}:validate_manifest"],
        "payload_manifest": manifest,
        "launch_configuration": launch_cfg,
        "telemetry_status": "standby",
    }


def calculate_trajectory(state: State) -> dict[str, Any]:
    """Performs trajectory analysis based on launch configuration."""
    cfg = state.get("launch_configuration", "unknown")
    # Mock trajectory calculation logic
    orbit = {
        "type": "GEO" if "Heavy" in cfg else "LEO",
        "inclination": 28.5,
        "altitude_km": 35786 if "Heavy" in cfg else 400,
    }

    return {
        "log": [f"{UNISPSC_CODE}:calculate_trajectory"],
        "orbit_parameters": orbit,
        "telemetry_status": "ready",
    }


def finalize_mission_plan(state: State) -> dict[str, Any]:
    """Finalizes the spacecraft mission plan and emits result."""
    orbit = state.get("orbit_parameters", {})
    manifest = state.get("payload_manifest", [])

    return {
        "log": [f"{UNISPSC_CODE}:finalize_mission_plan"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "mission_status": "GO for launch",
            "orbit_target": orbit.get("type"),
            "payload_count": len(manifest),
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_manifest", validate_manifest)
_g.add_node("calculate_trajectory", calculate_trajectory)
_g.add_node("finalize_mission_plan", finalize_mission_plan)

_g.add_edge(START, "validate_manifest")
_g.add_edge("validate_manifest", "calculate_trajectory")
_g.add_edge("calculate_trajectory", "finalize_mission_plan")
_g.add_edge("finalize_mission_plan", END)

graph = _g.compile()
