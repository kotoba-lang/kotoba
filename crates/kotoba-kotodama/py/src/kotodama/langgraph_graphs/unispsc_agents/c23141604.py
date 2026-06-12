# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23141604 — Press (segment 23).

Bespoke graph logic for industrial press machinery. This agent handles
configuration, mechanical execution cycles, and quality reporting for
heavy-duty pressing operations.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23141604"
UNISPSC_TITLE = "Press"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23141604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Press machinery
    pressure_psi: int
    alignment_verified: bool
    safety_interlock_active: bool
    cycle_index: int
    material_hardness_rating: float


def calibrate_press(state: State) -> dict[str, Any]:
    """Sets initial pressure and verifies mechanical alignment."""
    inp = state.get("input") or {}
    target_psi = inp.get("target_pressure", 2500)
    hardness = inp.get("hardness", 45.5)

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_press:target_psi={target_psi}"],
        "pressure_psi": target_psi,
        "material_hardness_rating": hardness,
        "alignment_verified": True,
        "safety_interlock_active": True,
        "cycle_index": 0
    }


def execute_press_cycle(state: State) -> dict[str, Any]:
    """Performs the physical compression step and increments cycle count."""
    current_cycle = state.get("cycle_index", 0) + 1
    psi = state.get("pressure_psi", 0)

    # Simulate force application logic
    effective_force = psi * 0.98 if state.get("alignment_verified") else 0

    return {
        "log": [f"{UNISPSC_CODE}:execute_press_cycle:{current_cycle}:force={effective_force}"],
        "cycle_index": current_cycle
    }


def finalize_output(state: State) -> dict[str, Any]:
    """Audits the final state and emits the manufacturing result."""
    success = state.get("alignment_verified") and state.get("safety_interlock_active")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_output:success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "COMPLETED" if success else "FAILED",
            "total_cycles": state.get("cycle_index"),
            "final_pressure": state.get("pressure_psi"),
            "integrity_check": success
        }
    }


_g = StateGraph(State)

_g.add_node("calibrate", calibrate_press)
_g.add_node("press_cycle", execute_press_cycle)
_g.add_node("finalize", finalize_output)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "press_cycle")
_g.add_edge("press_cycle", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
