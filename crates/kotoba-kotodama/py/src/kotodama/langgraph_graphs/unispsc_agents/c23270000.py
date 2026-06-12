# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23270000"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23270000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Welding
    welding_process_type: str  # TIG, MIG, ARC, etc.
    electrode_material: str
    shielding_gas_flow_rate: float
    integrity_score: float
    safety_interlock_active: bool


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the welding parameters and safety interlocks."""
    inp = state.get("input") or {}
    process = inp.get("process", "ARC")

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters -> process={process}"],
        "welding_process_type": process,
        "safety_interlock_active": True,
        "electrode_material": inp.get("electrode", "Standard Steel"),
    }


def perform_thermal_joining(state: State) -> dict[str, Any]:
    """Simulates the welding process using specified process type."""
    if not state.get("safety_interlock_active"):
        return {"log": [f"{UNISPSC_CODE}:perform_thermal_joining -> BLOCKED by safety"]}

    process = state.get("welding_process_type")
    return {
        "log": [f"{UNISPSC_CODE}:perform_thermal_joining -> executing {process} sequence"],
        "shielding_gas_flow_rate": 15.5,
        "integrity_score": 0.98,
    }


def certify_weld_quality(state: State) -> dict[str, Any]:
    """Performs non-destructive testing simulation and certifies result."""
    score = state.get("integrity_score", 0.0)
    passed = score > 0.90

    return {
        "log": [f"{UNISPSC_CODE}:certify_weld_quality -> score={score}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": passed,
            "telemetry": {
                "process": state.get("welding_process_type"),
                "integrity": score
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("join", perform_thermal_joining)
_g.add_node("certify", certify_weld_quality)

_g.add_edge(START, "validate")
_g.add_edge("validate", "join")
_g.add_edge("join", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
