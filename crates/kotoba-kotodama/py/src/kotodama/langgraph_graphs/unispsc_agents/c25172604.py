# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172604 — Mirror.
Commercial vehicle mirror component logic for safety and optical compliance.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172604"
UNISPSC_TITLE = "Mirror"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Mirror domain state fields
    coating_type: str
    is_dimmable: bool
    viewing_angle: int
    mount_point: str
    optical_purity: float


def inspect_specifications(state: State) -> dict[str, Any]:
    """Inspects the input for mirror coating and dimming capabilities."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "coating_type": inp.get("coating", "chrome"),
        "is_dimmable": inp.get("auto_dim", False),
    }


def calibrate_optics(state: State) -> dict[str, Any]:
    """Calculates viewing angle and optical purity based on coating."""
    coating = state.get("coating_type", "chrome")
    purity = 0.98 if coating == "silver" else 0.94
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_optics"],
        "viewing_angle": 120,
        "optical_purity": purity,
        "mount_point": "door_assembly"
    }


def finalize_catalog_entry(state: State) -> dict[str, Any]:
    """Aggregates all properties into the final result dictionary."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_catalog_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "coating": state.get("coating_type"),
                "auto_dim": state.get("is_dimmable"),
                "purity": state.get("optical_purity"),
                "angle": state.get("viewing_angle"),
                "mount": state.get("mount_point")
            },
            "status": "active"
        }
    }


_g = StateGraph(State)
_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("calibrate_optics", calibrate_optics)
_g.add_node("finalize_catalog_entry", finalize_catalog_entry)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "calibrate_optics")
_g.add_edge("calibrate_optics", "finalize_catalog_entry")
_g.add_edge("finalize_catalog_entry", END)

graph = _g.compile()
