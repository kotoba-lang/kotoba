# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111717 — Mine Ship (segment 25).

Bespoke graph logic for mine-laying and mine-countermeasures vessels.
Ensures operational readiness, ordnance verification, and mission reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111717"
UNISPSC_TITLE = "Mine Ship"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111717"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    hull_status: str
    ordnance_count: int
    deployment_zone: str
    mission_ready: bool


def inspect_vessel(state: State) -> dict[str, Any]:
    """Initial inspection of the mine ship systems."""
    inp = state.get("input") or {}
    hull = inp.get("hull_integrity", "optimal")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vessel -> {hull}"],
        "hull_status": hull,
        "mission_ready": hull == "optimal",
    }


def arm_ordnance(state: State) -> dict[str, Any]:
    """Verify and arm the mine-laying systems."""
    inp = state.get("input") or {}
    count = inp.get("requested_mines", 50)
    zone = inp.get("target_zone", "sector_alpha")

    log_entry = f"{UNISPSC_CODE}:arm_ordnance -> {count} units for {zone}"
    return {
        "log": [log_entry],
        "ordnance_count": count,
        "deployment_zone": zone,
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Compile final mission manifest and results."""
    is_ready = state.get("mission_ready", False)
    status = "DEPLOYED" if is_ready else "MAINTENANCE_REQUIRED"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch -> status: {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "vessel_status": status,
            "zone": state.get("deployment_zone"),
            "ordnance_on_board": state.get("ordnance_count"),
            "ok": is_ready,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_vessel", inspect_vessel)
_g.add_node("arm_ordnance", arm_ordnance)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "inspect_vessel")
_g.add_edge("inspect_vessel", "arm_ordnance")
_g.add_edge("arm_ordnance", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
