# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241617"
UNISPSC_TITLE = "Gear"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241617"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    gear_profile: str
    tooth_count: int
    material_spec: str
    validation_status: str


def validate_parameters(state: State) -> dict[str, Any]:
    """Inspect the gear request and normalize core design parameters."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "gear_profile": inp.get("profile", "involute"),
        "tooth_count": int(inp.get("teeth", 12)),
        "material_spec": inp.get("material", "ASTM-A48"),
    }


def check_mechanical_limits(state: State) -> dict[str, Any]:
    """Verify the gear design against standard mechanical constraints."""
    teeth = state.get("tooth_count", 0)
    # Industrial standard: gears usually require more than 5 teeth for kinematic validity
    status = "within_limits" if teeth > 5 else "undercut_risk"
    return {
        "log": [f"{UNISPSC_CODE}:check_mechanical_limits"],
        "validation_status": status,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Package the verified gear specification for the downstream manufacturer."""
    status = state.get("validation_status")
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mechanical_validation": status,
            "bom": {
                "profile": state.get("gear_profile"),
                "teeth": state.get("tooth_count"),
                "material": state.get("material_spec")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_parameters", validate_parameters)
_g.add_node("check_mechanical_limits", check_mechanical_limits)
_g.add_node("finalize_specification", finalize_specification)

_g.add_edge(START, "validate_parameters")
_g.add_edge("validate_parameters", "check_mechanical_limits")
_g.add_edge("check_mechanical_limits", "finalize_specification")
_g.add_edge("finalize_specification", END)

graph = _g.compile()
