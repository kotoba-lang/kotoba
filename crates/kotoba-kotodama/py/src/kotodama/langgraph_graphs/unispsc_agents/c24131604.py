# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24131604 — Lyophilizer (segment 24).

Bespoke graph logic for freeze-drying operations, simulating the thermal cycle
and vacuum control required for product stabilization.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24131604"
UNISPSC_TITLE = "Lyophilizer"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24131604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    vacuum_level_mtorr: float
    shelf_temp_celsius: float
    cycle_phase: str
    integrity_verified: bool


def initialize_batch(state: State) -> dict[str, Any]:
    """Pre-checks the equipment state and batch parameters."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "UNKNOWN")
    vial_count = inp.get("vial_count", 0)

    valid = vial_count > 0
    return {
        "log": [f"{UNISPSC_CODE}:initialize_batch - ID:{batch_id} vials:{vial_count}"],
        "cycle_phase": "loading",
        "shelf_temp_celsius": 20.0,
        "vacuum_level_mtorr": 760000.0,
        "integrity_verified": valid,
    }


def execute_sublimation(state: State) -> dict[str, Any]:
    """Simulates the primary drying phase by dropping temperature and pressure."""
    if not state.get("integrity_verified"):
        return {"log": [f"{UNISPSC_CODE}:execute_sublimation - ABORTED (integrity)"]}

    return {
        "log": [f"{UNISPSC_CODE}:execute_sublimation - freezing and vacuum pull down"],
        "cycle_phase": "primary_drying",
        "shelf_temp_celsius": -35.0,
        "vacuum_level_mtorr": 150.0,
    }


def finalize_process(state: State) -> dict[str, Any]:
    """Performs secondary drying and generates the final batch record."""
    success = state.get("integrity_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_process - cycle complete"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "success" if success else "error",
            "telemetry": {
                "phase": "secondary_drying",
                "temp": state.get("shelf_temp_celsius"),
                "vacuum": state.get("vacuum_level_mtorr"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_batch", initialize_batch)
_g.add_node("execute_sublimation", execute_sublimation)
_g.add_node("finalize_process", finalize_process)

_g.add_edge(START, "initialize_batch")
_g.add_edge("initialize_batch", "execute_sublimation")
_g.add_edge("execute_sublimation", "finalize_process")
_g.add_edge("finalize_process", END)

graph = _g.compile()
