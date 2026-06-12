# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102202 — Box sealing tape dispensers.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102202"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102202"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    tape_width_mm: float
    core_diameter_mm: float
    safety_shield_present: bool
    tension_control_active: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates physical dimensions for box sealing tape dispensers."""
    inp = state.get("input") or {}
    # Default to standard 2-inch (48mm) width and 3-inch (76.2mm) core
    width = float(inp.get("width_mm", 48.0))
    core = float(inp.get("core_mm", 76.2))
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs(width={width}mm)"],
        "tape_width_mm": width,
        "core_diameter_mm": core,
    }


def safety_audit(state: State) -> dict[str, Any]:
    """Checks for presence of safety features like blade shields."""
    inp = state.get("input") or {}
    shield = bool(inp.get("has_shield", True))
    tension = bool(inp.get("has_tension_control", True))
    return {
        "log": [f"{UNISPSC_CODE}:safety_audit(shield={shield})"],
        "safety_shield_present": shield,
        "tension_control_active": tension,
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalizes the state and constructs the result payload for the dispenser."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE or "Box Sealing Tape Dispenser",
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "width_mm": state.get("tape_width_mm"),
                "core_mm": state.get("core_diameter_mm"),
            },
            "features": {
                "safety_shield": state.get("safety_shield_present"),
                "tension_control": state.get("tension_control_active"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("safety_audit", safety_audit)
_g.add_node("finalize_asset", finalize_asset)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "safety_audit")
_g.add_edge("safety_audit", "finalize_asset")
_g.add_edge("finalize_asset", END)

graph = _g.compile()
