# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23141601 — Die Cast (segment 23).

Bespoke graph logic for high-pressure die casting process management.
This agent handles the configuration of alloy/mold parameters, execution
of the casting cycle, and final part inspection.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23141601"
UNISPSC_TITLE = "Die Cast"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23141601"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Die Cast operations
    alloy_type: str
    mold_id: str
    injection_pressure_psi: int
    cycle_time_sec: float
    inspection_passed: bool


def setup_casting_parameters(state: State) -> dict[str, Any]:
    """Node: Configures the die casting machine based on material requirements."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "A380 Aluminum")
    mold = inp.get("mold_reference", "MOLD-X100")

    return {
        "log": [f"{UNISPSC_CODE}:setup_casting_parameters -> {alloy} using {mold}"],
        "alloy_type": alloy,
        "mold_id": mold,
        "injection_pressure_psi": inp.get("pressure", 1500),
    }


def execute_injection_cycle(state: State) -> dict[str, Any]:
    """Node: Manages the actual metal injection and cooling duration."""
    pressure = state.get("injection_pressure_psi", 1000)
    # Simulated physics: higher pressure requires slightly longer cooling
    calculated_cycle = 12.0 + (pressure / 500.0)

    return {
        "log": [f"{UNISPSC_CODE}:execute_injection_cycle -> cycle completed in {calculated_cycle:.1f}s"],
        "cycle_time_sec": calculated_cycle,
    }


def perform_quality_inspection(state: State) -> dict[str, Any]:
    """Node: Validates the physical properties of the resulting cast part."""
    cycle_time = state.get("cycle_time_sec", 0.0)
    # Quality threshold: cycle time must be within nominal range for structural integrity
    passed = 10.0 <= cycle_time <= 25.0

    return {
        "log": [f"{UNISPSC_CODE}:perform_quality_inspection -> passed: {passed}"],
        "inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "process_data": {
                "alloy": state.get("alloy_type"),
                "pressure_psi": state.get("injection_pressure_psi"),
                "cycle_time": cycle_time,
            },
            "status": "COMPLETED" if passed else "REJECTED",
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("setup", setup_casting_parameters)
_g.add_node("inject", execute_injection_cycle)
_g.add_node("inspect", perform_quality_inspection)

_g.add_edge(START, "setup")
_g.add_edge("setup", "inject")
_g.add_edge("inject", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
