# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102000 — Harvest (segment 21).

Bespoke logic for managing harvest operations, yield tracking, and quality
assessment within the Farming, Fishing, Forestry, and Wildlife machinery segment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102000"
UNISPSC_TITLE = "Harvest"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    commodity_type: str
    yield_estimate: float
    harvest_status: str
    quality_verified: bool
    storage_bin_id: str


def plan_harvest(state: State) -> dict[str, Any]:
    """Validates input parameters and prepares the harvest plan."""
    inp = state.get("input") or {}
    commodity = str(inp.get("commodity", "crop"))
    estimate = float(inp.get("estimate", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:plan_harvest -> {commodity}"],
        "commodity_type": commodity,
        "yield_estimate": estimate,
        "harvest_status": "planned",
    }


def execute_harvest(state: State) -> dict[str, Any]:
    """Simulates the harvesting process and records yield metrics."""
    commodity = state.get("commodity_type", "crop")
    estimate = state.get("yield_estimate", 0.0)

    # Simulate a successful harvest with nominal yield loss during collection
    actual_yield = estimate * 0.95

    return {
        "log": [f"{UNISPSC_CODE}:execute_harvest -> yield: {actual_yield:.2f}"],
        "harvest_status": "completed",
        "quality_verified": True,
        "storage_bin_id": f"BIN-{commodity.upper()}-42",
    }


def finalize_harvest(state: State) -> dict[str, Any]:
    """Finalizes records and emits the harvest summary."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_harvest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "commodity": state.get("commodity_type"),
            "final_status": state.get("harvest_status"),
            "storage_assignment": state.get("storage_bin_id"),
            "did": UNISPSC_DID,
            "ok": state.get("quality_verified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("plan_harvest", plan_harvest)
_g.add_node("execute_harvest", execute_harvest)
_g.add_node("finalize_harvest", finalize_harvest)

_g.add_edge(START, "plan_harvest")
_g.add_edge("plan_harvest", "execute_harvest")
_g.add_edge("execute_harvest", "finalize_harvest")
_g.add_edge("finalize_harvest", END)

graph = _g.compile()
