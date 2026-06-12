# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202400 — Aircraft Fuel (segment 25).
Bespoke logic for fuel quality verification, safety inspection, and storage allocation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202400"
UNISPSC_TITLE = "Aircraft Fuel"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202400"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    fuel_grade: str
    purity_level: float
    storage_tank: str
    is_safe_for_flight: bool


def inspect_quality(state: State) -> dict[str, Any]:
    """Perform chemical analysis simulation on incoming fuel batch."""
    inp = state.get("input") or {}
    # Simulate extraction of quality metrics from input telemetry or request
    purity = float(inp.get("purity", 0.995))
    grade = str(inp.get("grade", "JET-A1"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_quality"],
        "purity_level": purity,
        "fuel_grade": grade,
        "is_safe_for_flight": purity >= 0.998
    }


def assign_storage(state: State) -> dict[str, Any]:
    """Determine optimal storage based on fuel grade and safety status."""
    grade = state.get("fuel_grade", "UNKNOWN")
    is_safe = state.get("is_safe_for_flight", False)

    # Logic to divert contaminated fuel or assign to specific grade tanks
    if not is_safe:
        tank = "QUARANTINE-ALPHA-01"
    elif grade == "JET-A1":
        tank = "MAIN-RESERVOIR-A"
    else:
        tank = "AUX-TANK-B"

    return {
        "log": [f"{UNISPSC_CODE}:assign_storage"],
        "storage_tank": tank
    }


def finalize_inventory(state: State) -> dict[str, Any]:
    """Update inventory records and generate release manifest for the aircraft fuel."""
    is_safe = state.get("is_safe_for_flight", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_safe else "REJECTED",
            "metadata": {
                "tank_allocation": state.get("storage_tank"),
                "grade_verified": state.get("fuel_grade"),
                "purity_rating": state.get("purity_level")
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_quality", inspect_quality)
_g.add_node("assign_storage", assign_storage)
_g.add_node("finalize_inventory", finalize_inventory)

_g.add_edge(START, "inspect_quality")
_g.add_edge("inspect_quality", "assign_storage")
_g.add_edge("assign_storage", "finalize_inventory")
_g.add_edge("finalize_inventory", END)

graph = _g.compile()
