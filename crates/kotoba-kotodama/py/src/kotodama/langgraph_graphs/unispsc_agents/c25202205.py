# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202205 — Aircraft Tire.
Bespoke logic for managing aircraft tire lifecycle and safety inspections.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202205"
UNISPSC_TITLE = "Aircraft Tire"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202205"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    tire_pressure_psi: float
    tread_depth_mm: float
    safety_inspection_passed: bool
    maintenance_log_id: str


def inspect_tire(state: State) -> dict[str, Any]:
    """Node: Validate tire physical parameters from input."""
    inp = state.get("input") or {}
    pressure = float(inp.get("tire_pressure_psi", 0.0))
    tread = float(inp.get("tread_depth_mm", 0.0))
    log_id = str(inp.get("maintenance_log_id", "UNKNOWN-000"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_tire: pressure={pressure}, tread={tread}"],
        "tire_pressure_psi": pressure,
        "tread_depth_mm": tread,
        "maintenance_log_id": log_id,
    }


def evaluate_airworthiness(state: State) -> dict[str, Any]:
    """Node: Process airworthiness based on aviation safety standards."""
    pressure = state.get("tire_pressure_psi", 0.0)
    tread = state.get("tread_depth_mm", 0.0)

    # Aircraft tires require precise pressure and minimum tread depth.
    # Typical safety range for this class of tire: 180-220 PSI and >2.0mm tread.
    is_safe = 180.0 <= pressure <= 220.0 and tread >= 2.0

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_airworthiness: passed={is_safe}"],
        "safety_inspection_passed": is_safe,
    }


def finalize_report(state: State) -> dict[str, Any]:
    """Node: Emit final inspection certificate."""
    is_safe = state.get("safety_inspection_passed", False)
    log_id = state.get("maintenance_log_id", "N/A")

    status = "CERTIFIED_FOR_FLIGHT" if is_safe else "REJECTED_MAINTENANCE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_report: status={status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "airworthiness_status": status,
            "maintenance_log_id": log_id,
            "inspection_completed": True,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_tire)
_g.add_node("evaluate", evaluate_airworthiness)
_g.add_node("finalize", finalize_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
