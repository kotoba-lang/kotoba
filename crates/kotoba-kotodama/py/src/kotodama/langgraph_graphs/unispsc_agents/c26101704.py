# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101704 — Mount (segment 26).

Bespoke graph logic for structural and mechanical mounting components.
This agent validates mechanical interfaces, load ratings, and vibration
damping specifications for power generation and distribution hardware.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101704"
UNISPSC_TITLE = "Mount"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    interface_type: str
    load_capacity_kg: float
    vibration_isolation_certified: bool
    structural_integrity_score: float


def validate_requirements(state: State) -> dict[str, Any]:
    """Inspects input for mounting interface and load requirements."""
    inp = state.get("input") or {}
    interface = inp.get("interface", "standard_flange")
    load = float(inp.get("load_kg", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements -> interface:{interface}, load:{load}kg"],
        "interface_type": interface,
        "load_capacity_kg": load,
    }


def evaluate_structural_fit(state: State) -> dict[str, Any]:
    """Calculates structural integrity based on interface and load."""
    load = state.get("load_capacity_kg", 0.0)
    # Dummy logic: mounts in this segment typically handle up to 5000kg
    score = 1.0 if load <= 5000 else 0.5
    vibration_req = state.get("input", {}).get("vibration_damping", False)

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_structural_fit -> score:{score}"],
        "structural_integrity_score": score,
        "vibration_isolation_certified": vibration_req and score > 0.8,
    }


def finalize_mount_config(state: State) -> dict[str, Any]:
    """Emits the final mounting configuration and compliance status."""
    is_valid = state.get("structural_integrity_score", 0.0) > 0.7

    return {
        "log": [f"{UNISPSC_CODE}:finalize_mount_config -> valid:{is_valid}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_valid else "REJECTED",
            "specifications": {
                "interface": state.get("interface_type"),
                "max_load": state.get("load_capacity_kg"),
                "vibration_certified": state.get("vibration_isolation_certified"),
            },
            "integrity_score": state.get("structural_integrity_score"),
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_requirements)
_g.add_node("evaluate", evaluate_structural_fit)
_g.add_node("finalize", finalize_mount_config)

_g.add_edge(START, "validate")
_g.add_edge("validate", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
