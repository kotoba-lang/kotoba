# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173802 — Axle (segment 25).

Bespoke graph logic for axle specification validation, alignment calibration,
and result emission. This agent ensures axle components meet required load
capacities and manufacturing standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173802"
UNISPSC_TITLE = "Axle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173802"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Axle
    axle_type: str
    load_capacity_kg: float
    inspection_passed: bool
    manufacturing_batch: str


def validate_specs(state: State) -> dict[str, Any]:
    """Verifies input specifications for the axle unit."""
    inp = state.get("input") or {}
    axle_type = inp.get("type", "rigid")
    load_cap = float(inp.get("load_capacity", 2000.0))
    batch = inp.get("batch_id", "ST-2517-A")

    # Simple validation logic: capacity must be positive
    is_valid = load_cap > 0 and len(batch) > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "axle_type": axle_type,
        "load_capacity_kg": load_cap,
        "inspection_passed": is_valid,
        "manufacturing_batch": batch,
    }


def calibrate_alignment(state: State) -> dict[str, Any]:
    """Performs virtual calibration of axle alignment."""
    # Logic: Calibration status depends on inspection result
    status = "calibrated" if state.get("inspection_passed") else "failed_pre_check"
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_alignment:{status}"],
    }


def emit_result(state: State) -> dict[str, Any]:
    """Finalizes the axle record and emits the processing result."""
    ok = state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "axle_specification": {
                "type": state.get("axle_type"),
                "capacity": state.get("load_capacity_kg"),
                "batch": state.get("manufacturing_batch"),
            },
            "status": "certified" if ok else "quarantined",
            "did": UNISPSC_DID,
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("calibrate", calibrate_alignment)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
