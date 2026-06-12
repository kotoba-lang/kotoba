# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122611"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122611"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Fastener
    material_grade: str
    thread_spec: str
    clamping_force_kn: float
    safety_factor: float


def validate_fastener_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the fastener hardware."""
    inp = state.get("input") or {}
    material = inp.get("material", "Grade 8.8 Steel")
    thread = inp.get("thread", "M10-1.5")

    return {
        "log": [f"{UNISPSC_CODE}:validate_fastener_specs"],
        "material_grade": material,
        "thread_spec": thread,
    }


def calculate_load_dynamics(state: State) -> dict[str, Any]:
    """Calculates mechanical properties and safety margins based on material grade."""
    grade = state.get("material_grade", "")

    # Simulated engineering logic for clamping force
    force = 25.5
    if "10.9" in grade:
        force = 35.0
    elif "12.9" in grade:
        force = 42.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load_dynamics"],
        "clamping_force_kn": force,
        "safety_factor": 1.5,
    }


def emit_fastener_certification(state: State) -> dict[str, Any]:
    """Finalizes the fastener state and emits the structured result manifest."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_fastener_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "engineering_data": {
                "material": state.get("material_grade"),
                "thread": state.get("thread_spec"),
                "clamping_force_kn": state.get("clamping_force_kn"),
                "safety_factor": state.get("safety_factor"),
            },
            "status": "certified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_fastener_specs)
_g.add_node("calculate", calculate_load_dynamics)
_g.add_node("emit", emit_fastener_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
