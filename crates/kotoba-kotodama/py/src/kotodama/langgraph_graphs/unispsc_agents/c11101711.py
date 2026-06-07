# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101711"
UNISPSC_TITLE = "Proc"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101711"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for "Proc" (Live Animal specimen)
    health_status: str
    quarantine_verified: bool
    specimen_weight_kg: float
    transport_lot_id: str


def validate_specimen(state: State) -> dict[str, Any]:
    """Validates the intake of a Proc specimen and sets initial identity."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    is_valid = inp.get("species_code") == UNISPSC_CODE or weight > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specimen"],
        "specimen_weight_kg": weight,
        "transport_lot_id": inp.get("lot_id", "LOT-TEMP-000"),
        "quarantine_verified": False if weight < 1.0 else True
    }


def conduct_health_screening(state: State) -> dict[str, Any]:
    """Evaluates the health status of the Proc specimen based on physical metrics."""
    weight = state.get("specimen_weight_kg", 0.0)

    if weight > 2.5:
        status = "optimal"
    elif weight > 0.5:
        status = "observation_required"
    else:
        status = "critical"

    return {
        "log": [f"{UNISPSC_CODE}:conduct_health_screening"],
        "health_status": status
    }


def register_proc_entry(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and emits the result manifest."""
    status = state.get("health_status", "unknown")
    verified = state.get("quarantine_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:register_proc_entry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "manifest": {
                "lot": state.get("transport_lot_id"),
                "health": status,
                "cleared": verified and status != "critical"
            },
            "status": "completed"
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specimen)
_g.add_node("screen", conduct_health_screening)
_g.add_node("register", register_proc_entry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "screen")
_g.add_edge("screen", "register")
_g.add_edge("register", END)

graph = _g.compile()
