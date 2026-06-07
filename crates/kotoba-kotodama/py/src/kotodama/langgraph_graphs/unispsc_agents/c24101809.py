# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101809 — Dock (segment 24).

Bespoke graph logic for handling docking operations, berth assignment,
and safety verification within a port or terminal environment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101809"
UNISPSC_TITLE = "Dock"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101809"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Dock
    vessel_id: str
    berth_assigned: str
    safety_inspection_passed: bool
    mooring_depth_m: float
    docking_permit_id: str


def schedule_berth(state: State) -> dict[str, Any]:
    """Identify the vessel and assign an available berth based on input."""
    inp = state.get("input") or {}
    vessel = inp.get("vessel_id", "UNKNOWN_VESSEL")
    # Simple deterministic berth assignment
    berth_num = abs(hash(vessel)) % 50
    berth_id = f"BERTH-{berth_num:02d}"

    return {
        "log": [f"{UNISPSC_CODE}:schedule_berth -> {berth_id}"],
        "vessel_id": vessel,
        "berth_assigned": berth_id,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Perform clearance checks for mooring and depth requirements."""
    inp = state.get("input") or {}
    required_depth = float(inp.get("depth_requirement_m", 12.0))
    # Dock capacity: max 25m depth
    is_safe = 0 < required_depth <= 25.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety -> {'clear' if is_safe else 'depth_alert'}"],
        "safety_inspection_passed": is_safe,
        "mooring_depth_m": required_depth,
    }


def finalize_docking(state: State) -> dict[str, Any]:
    """Issue a docking permit and return the final status of the operation."""
    vessel = state.get("vessel_id", "UNK")
    berth = state.get("berth_assigned", "NONE")
    passed = state.get("safety_inspection_passed", False)

    permit_id = f"PRMT-{vessel[:3].upper()}-{berth}" if passed else "NONE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_docking"],
        "docking_permit_id": permit_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "vessel": vessel,
            "berth": berth,
            "permit": permit_id,
            "status": "DOCKING_APPROVED" if passed else "DOCKING_DENIED",
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("schedule_berth", schedule_berth)
_g.add_node("verify_safety", verify_safety)
_g.add_node("finalize_docking", finalize_docking)

_g.add_edge(START, "schedule_berth")
_g.add_edge("schedule_berth", "verify_safety")
_g.add_edge("verify_safety", "finalize_docking")
_g.add_edge("finalize_docking", END)

graph = _g.compile()
