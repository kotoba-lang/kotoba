# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241608"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241608"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    material_hardness: float
    surface_finish_target: str
    coolant_flow_rate: float
    operation_confirmed: bool


def validate_material(state: State) -> dict[str, Any]:
    """Validates the input material characteristics for industrial processing."""
    inp = state.get("input") or {}
    # Default hardness for standard alloy steel if not provided
    hardness = float(inp.get("hardness", 180.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "material_hardness": hardness,
    }


def calibrate_machinery(state: State) -> dict[str, Any]:
    """Calibrates machinery settings based on material hardness."""
    hardness = state.get("material_hardness", 180.0)
    # Higher hardness requires increased coolant flow to maintain tool life
    coolant = 8.5 if hardness < 250 else 15.0
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_machinery"],
        "coolant_flow_rate": coolant,
        "surface_finish_target": "Ra 1.6",
    }


def finalize_operation(state: State) -> dict[str, Any]:
    """Finalizes the manufacturing process and emits the execution result."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_operation"],
        "operation_confirmed": True,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "material_hardness": state.get("material_hardness"),
                "coolant_l_min": state.get("coolant_flow_rate"),
                "surface_finish": state.get("surface_finish_target"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_material", validate_material)
_g.add_node("calibrate_machinery", calibrate_machinery)
_g.add_node("finalize_operation", finalize_operation)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "calibrate_machinery")
_g.add_edge("calibrate_machinery", "finalize_operation")
_g.add_edge("finalize_operation", END)

graph = _g.compile()
