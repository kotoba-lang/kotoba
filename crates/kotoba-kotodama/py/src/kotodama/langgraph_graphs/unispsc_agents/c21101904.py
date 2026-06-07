# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101904 — Sprayer (segment 21).

Bespoke logic for managing agricultural or landscape spray equipment operations,
ensuring pressure calibration and safety compliance.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101904"
UNISPSC_TITLE = "Sprayer"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101904"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Extra domain fields for "Sprayer"
    pressure_psi: int
    nozzle_setting: str
    fluid_type: str
    safety_lock_engaged: bool


def validate_equipment(state: State) -> dict[str, Any]:
    """Validate safety protocols and fluid compatibility."""
    inp = state.get("input") or {}
    fluid = inp.get("fluid", "water")
    safety = inp.get("safety_check", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_equipment"],
        "fluid_type": fluid,
        "safety_lock_engaged": not safety,
    }


def calibrate_pressure(state: State) -> dict[str, Any]:
    """Calibrate pressure settings based on the nozzle type."""
    inp = state.get("input") or {}
    nozzle = inp.get("nozzle", "standard_cone")

    # Logic simulation: high pressure for jet, low for mist
    pressure = 45 if nozzle == "jet" else 20

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_pressure"],
        "nozzle_setting": nozzle,
        "pressure_psi": pressure,
    }


def execute_spray(state: State) -> dict[str, Any]:
    """Execute the spraying operation and record metrics."""
    if state.get("safety_lock_engaged"):
        status = "blocked_by_safety"
    else:
        status = "operational"

    return {
        "log": [f"{UNISPSC_CODE}:execute_spray"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": status,
            "psi_final": state.get("pressure_psi"),
            "ok": not state.get("safety_lock_engaged"),
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_equipment)
_g.add_node("calibrate", calibrate_pressure)
_g.add_node("execute", execute_spray)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
