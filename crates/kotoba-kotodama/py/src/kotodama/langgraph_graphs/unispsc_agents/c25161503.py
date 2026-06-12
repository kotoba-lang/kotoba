# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25161503 — Tricycle (segment 25).
Bespoke LangGraph logic for tricycle assembly and quality verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25161503"
UNISPSC_TITLE = "Tricycle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25161503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Tricycle
    frame_integrity: bool
    wheel_alignment: bool
    safety_brake_test: bool
    serial_id: str


def structural_inspection(state: State) -> dict[str, Any]:
    """Inspect the frame and structural integrity of the tricycle components."""
    inp = state.get("input") or {}
    model = inp.get("model", "Standard")
    # Simulation: frames are generally solid unless specified as low-grade material
    is_solid = inp.get("material") != "polymer_reject"

    return {
        "log": [f"{UNISPSC_CODE}:structural_inspection model={model}"],
        "frame_integrity": is_solid,
    }


def mechanical_tuning(state: State) -> dict[str, Any]:
    """Align wheels and calibrate the mechanical parts of the tricycle assembly."""
    # Ensure all three wheels are aligned and pedals are calibrated
    tuning_id = f"TRI-{UNISPSC_CODE}-{id(state) % 10000:04d}"

    return {
        "log": [f"{UNISPSC_CODE}:mechanical_tuning status=ALIGNED"],
        "wheel_alignment": True,
        "serial_id": tuning_id,
    }


def final_certification(state: State) -> dict[str, Any]:
    """Perform safety tests and issue the final certificate of compliance for the Tricycle."""
    is_safe = state.get("frame_integrity", False) and state.get("wheel_alignment", False)

    return {
        "log": [f"{UNISPSC_CODE}:final_certification safety_passed={is_safe}"],
        "safety_brake_test": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial_id": state.get("serial_id"),
            "status": "CERTIFIED" if is_safe else "REJECTED",
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("structural_inspection", structural_inspection)
_g.add_node("mechanical_tuning", mechanical_tuning)
_g.add_node("final_certification", final_certification)

_g.add_edge(START, "structural_inspection")
_g.add_edge("structural_inspection", "mechanical_tuning")
_g.add_edge("mechanical_tuning", "final_certification")
_g.add_edge("final_certification", END)

graph = _g.compile()
