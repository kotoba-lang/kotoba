# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25174203 — Ball Joint (segment 25).
Bespoke logic for mechanical joint inspection, articulation testing, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25174203"
UNISPSC_TITLE = "Ball Joint"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25174203"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Ball Joint mechanical state
    wear_tolerance_mm: float
    articulation_angle_deg: float
    lubrication_quality: str
    seal_integrity_verified: bool


def inspect_component(state: State) -> dict[str, Any]:
    """Inspects the physical wear and seal integrity of the ball joint."""
    inp = state.get("input") or {}
    # Simulate extraction of telemetry or inspection data
    wear = float(inp.get("measured_wear", 0.02))
    seal_ok = wear < 0.5  # Tolerance threshold
    return {
        "log": [f"{UNISPSC_CODE}:inspect_component: wear={wear}mm, seal={seal_ok}"],
        "wear_tolerance_mm": wear,
        "seal_integrity_verified": seal_ok,
    }


def verify_articulation(state: State) -> dict[str, Any]:
    """Tests the range of motion and determines lubrication status."""
    # Simulation of articulation testing logic
    angle = 38.5
    wear = state.get("wear_tolerance_mm", 0.0)

    if wear > 0.3:
        lubrication = "Degraded"
    else:
        lubrication = "Optimal"

    return {
        "log": [f"{UNISPSC_CODE}:verify_articulation: range={angle}°, lube={lubrication}"],
        "articulation_angle_deg": angle,
        "lubrication_quality": lubrication,
    }


def certify_unit(state: State) -> dict[str, Any]:
    """Finalizes the mechanical certification based on collected metrics."""
    wear = state.get("wear_tolerance_mm", 1.0)
    seal = state.get("seal_integrity_verified", False)
    lube = state.get("lubrication_quality", "Unknown")

    is_serviceable = wear < 0.4 and seal and lube == "Optimal"

    return {
        "log": [f"{UNISPSC_CODE}:certify_unit: serviceable={is_serviceable}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "disposition": "Certified" if is_serviceable else "Requires Maintenance",
            "metrics": {
                "wear_mm": wear,
                "angle_deg": state.get("articulation_angle_deg"),
                "lubrication": lube
            },
            "ok": is_serviceable,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_component)
_g.add_node("verify", verify_articulation)
_g.add_node("certify", certify_unit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
