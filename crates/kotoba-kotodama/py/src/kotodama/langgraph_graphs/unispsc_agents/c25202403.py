# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202403 — Tank (segment 25).

Bespoke logic for armored vehicle readiness and tank systems validation.
This agent manages the structural, offensive, and propulsion verification
cycles for armored combat vehicles.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202403"
UNISPSC_TITLE = "Tank"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202403"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Tank
    hull_integrity: bool
    weapon_systems_calibrated: bool
    propulsion_status: str
    fuel_level_percent: float


def structural_audit(state: State) -> dict[str, Any]:
    """Inspects the armored hull and structural integrity of the tank."""
    inp = state.get("input") or {}
    armor_rating = inp.get("armor_rating", 0)
    # Threshold for heavy armor validation
    is_solid = armor_rating >= 100
    return {
        "log": [f"{UNISPSC_CODE}:structural_audit"],
        "hull_integrity": is_solid,
    }


def systems_calibration(state: State) -> dict[str, Any]:
    """Calibrates the main cannon and digital fire control systems."""
    return {
        "log": [f"{UNISPSC_CODE}:systems_calibration"],
        "weapon_systems_calibrated": True,
    }


def engine_certification(state: State) -> dict[str, Any]:
    """Checks the multi-fuel turbine engine and drivetrain performance."""
    inp = state.get("input") or {}
    fuel = float(inp.get("fuel", 100.0))
    return {
        "log": [f"{UNISPSC_CODE}:engine_certification"],
        "propulsion_status": "certified" if fuel > 20 else "low_fuel_warning",
        "fuel_level_percent": fuel,
    }


def assemble_readiness_report(state: State) -> dict[str, Any]:
    """Finalizes the readiness report for the armored unit."""
    hull_ok = state.get("hull_integrity", False)
    weapons_ok = state.get("weapon_systems_calibrated", False)
    propulsion_ok = state.get("propulsion_status") == "certified"

    is_ready = hull_ok and weapons_ok and propulsion_ok

    return {
        "log": [f"{UNISPSC_CODE}:assemble_readiness_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "readiness": "mission_capable" if is_ready else "non_mission_capable",
            "ok": is_ready,
            "telemetry": {
                "armor": "verified" if hull_ok else "failed",
                "armament": "calibrated" if weapons_ok else "pending",
                "fuel": f"{state.get('fuel_level_percent', 0)}%"
            }
        },
    }


_g = StateGraph(State)
_g.add_node("structural_audit", structural_audit)
_g.add_node("systems_calibration", systems_calibration)
_g.add_node("engine_certification", engine_certification)
_g.add_node("assemble_readiness_report", assemble_readiness_report)

_g.add_edge(START, "structural_audit")
_g.add_edge("structural_audit", "systems_calibration")
_g.add_edge("systems_calibration", "engine_certification")
_g.add_edge("engine_certification", "assemble_readiness_report")
_g.add_edge("assemble_readiness_report", END)

graph = _g.compile()
