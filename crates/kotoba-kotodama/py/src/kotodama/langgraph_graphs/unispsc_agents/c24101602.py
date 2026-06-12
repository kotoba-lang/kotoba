# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101602"
UNISPSC_TITLE = "Hoist"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Hoist
    hoist_load_limit_kg: float
    is_emergency_stop_active: bool
    hoist_certification_valid: bool
    operation_mode: str


def initialize_hoist_operation(state: State) -> dict[str, Any]:
    """Prepares the hoist for operation based on input parameters."""
    inp = state.get("input") or {}
    load_limit = float(inp.get("load_limit", 2000.0))
    mode = str(inp.get("mode", "standard"))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_hoist_operation"],
        "hoist_load_limit_kg": load_limit,
        "operation_mode": mode,
        "is_emergency_stop_active": False,
    }


def verify_hoist_safety(state: State) -> dict[str, Any]:
    """Checks safety protocols and certification status."""
    limit = state.get("hoist_load_limit_kg", 0.0)
    # Logic: Hoists over 5000kg require special certification check
    cert_valid = limit <= 5000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_hoist_safety:cert_valid={cert_valid}"],
        "hoist_certification_valid": cert_valid,
    }


def execute_hoist_cycle(state: State) -> dict[str, Any]:
    """Records the hoist operation cycle results."""
    is_safe = state.get("hoist_certification_valid", False)
    mode = state.get("operation_mode", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:execute_hoist_cycle"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "COMPLETED" if is_safe else "BLOCKED_SAFETY",
            "telemetry": {
                "mode": mode,
                "load_limit": state.get("hoist_load_limit_kg")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_hoist_operation)
_g.add_node("verify", verify_hoist_safety)
_g.add_node("execute", execute_hoist_cycle)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "verify")
_g.add_edge("verify", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
