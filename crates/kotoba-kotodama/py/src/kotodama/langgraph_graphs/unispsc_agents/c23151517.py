# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151517"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151517"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    welding_process: str
    material_spec: str
    temperature_celsius: int
    weld_integrity_score: float


def setup_welding_job(state: State) -> dict[str, Any]:
    """Initialize welding parameters from input or defaults."""
    inp = state.get("input") or {}
    process = inp.get("process", "Gas Metal Arc Welding (GMAW)")
    material = inp.get("material", "ASTM A36 Structural Steel")

    return {
        "log": [f"{UNISPSC_CODE}:setup_welding_job -> {process}"],
        "welding_process": process,
        "material_spec": material,
        "temperature_celsius": 1500,
    }


def execute_thermal_bond(state: State) -> dict[str, Any]:
    """Simulate the physical welding process."""
    process = state.get("welding_process", "")
    temp = state.get("temperature_celsius", 0)

    # Simple logic: higher temp (within range) and specific processes yield better scores
    integrity = 0.98 if "Gas" in process and temp >= 1450 else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:execute_thermal_bond -> temperature {temp}C"],
        "weld_integrity_score": integrity,
    }


def inspect_and_certify(state: State) -> dict[str, Any]:
    """Validate the weld and emit the final result."""
    score = state.get("weld_integrity_score", 0.0)
    is_valid = score >= 0.90

    return {
        "log": [f"{UNISPSC_CODE}:inspect_and_certify -> integrity {score}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_valid else "FAILED_INSPECTION",
            "process_used": state.get("welding_process"),
            "integrity_score": score,
            "ok": is_valid,
        },
    }


_g = StateGraph(State)
_g.add_node("setup", setup_welding_job)
_g.add_node("bond", execute_thermal_bond)
_g.add_node("inspect", inspect_and_certify)

_g.add_edge(START, "setup")
_g.add_edge("setup", "bond")
_g.add_edge("bond", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
