# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271808 — Flux.
Handles characterization and verification of industrial flux supplies.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271808"
UNISPSC_TITLE = "Flux"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271808"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Flux (Industrial Supply)
    chemistry_category: str
    activation_temperature: float
    residue_standard: str
    safety_certified: bool

def inspect_composition(state: State) -> dict[str, Any]:
    """Identify the chemical basis and residue characteristics of the flux."""
    inp = state.get("input") or {}
    material = inp.get("material", "rosin-mildly-activated")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "chemistry_category": material,
        "residue_standard": "IPC-J-STD-004"
    }

def verify_thermal_activation(state: State) -> dict[str, Any]:
    """Verify the flux activation range against welding process requirements."""
    inp = state.get("input") or {}
    target_temp = float(inp.get("target_process_temp", 220.0))

    # Simple logic: flux must activate below the target process temperature
    activation = 150.0 if state.get("chemistry_category") == "rosin-mildly-activated" else 200.0
    is_safe = activation < target_temp

    return {
        "log": [f"{UNISPSC_CODE}:verify_thermal_activation"],
        "activation_temperature": activation,
        "safety_certified": is_safe
    }

def cert_and_emit(state: State) -> dict[str, Any]:
    """Finalize the supply certification and emit the result."""
    ok = state.get("safety_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:cert_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": {
                "category": state.get("chemistry_category"),
                "activation_point": state.get("activation_temperature"),
                "standard": state.get("residue_standard"),
                "compliant": ok
            },
            "ok": ok
        }
    }

_g = StateGraph(State)
_g.add_node("inspect", inspect_composition)
_g.add_node("verify", verify_thermal_activation)
_g.add_node("finalize", cert_and_emit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
