# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181701 — Trailer (segment 25).
Bespoke logic for chassis inspection, load capacity verification, and registration.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181701"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Trailer processing
    chassis_inspection_passed: bool
    weight_within_limit: bool
    registration_id: str
    axle_count: int


def inspect_chassis(state: State) -> dict[str, Any]:
    """Inspects the structural integrity of the trailer chassis."""
    inp = state.get("input") or {}
    inspection_data = inp.get("inspection", {})
    passed = inspection_data.get("structural_integrity", False)
    axles = inspection_data.get("axles", 2)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_chassis"],
        "chassis_inspection_passed": passed,
        "axle_count": axles,
    }


def verify_load_capacity(state: State) -> dict[str, Any]:
    """Checks if the intended load is within the trailer's rated capacity."""
    if not state.get("chassis_inspection_passed"):
        return {
            "log": [f"{UNISPSC_CODE}:verify_load_capacity:skipped"],
            "weight_within_limit": False,
        }

    inp = state.get("input") or {}
    load_weight = inp.get("load_weight", 0)
    capacity = inp.get("max_capacity", 5000)

    ok = load_weight <= capacity
    return {
        "log": [f"{UNISPSC_CODE}:verify_load_capacity:{'ok' if ok else 'exceeded'}"],
        "weight_within_limit": ok,
    }


def issue_registration(state: State) -> dict[str, Any]:
    """Finalizes processing and issues a registration ID if all checks pass."""
    ok = state.get("chassis_inspection_passed", False) and state.get("weight_within_limit", False)
    reg_id = f"REG-{UNISPSC_CODE}-{id(state) % 10000}" if ok else "INCOMPLETE"

    return {
        "log": [f"{UNISPSC_CODE}:issue_registration"],
        "registration_id": reg_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "registration_id": reg_id,
            "status": "registered" if ok else "failed",
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_chassis", inspect_chassis)
_g.add_node("verify_load_capacity", verify_load_capacity)
_g.add_node("issue_registration", issue_registration)

_g.add_edge(START, "inspect_chassis")
_g.add_edge("inspect_chassis", "verify_load_capacity")
_g.add_edge("verify_load_capacity", "issue_registration")
_g.add_edge("issue_registration", END)

graph = _g.compile()
