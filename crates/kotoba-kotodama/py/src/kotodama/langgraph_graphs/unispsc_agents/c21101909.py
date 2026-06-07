# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101909"
UNISPSC_TITLE = "Planting"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101909"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    soil_ph: float
    moisture_index: float
    planting_depth_mm: int
    seeds_sown: int
    site_prepared: bool


def prepare_site(state: State) -> dict[str, Any]:
    """Assesses soil conditions and prepares the ground for planting."""
    inp = state.get("input") or {}
    ph = float(inp.get("soil_ph", 6.8))
    moisture = float(inp.get("moisture", 0.4))

    return {
        "log": [f"{UNISPSC_CODE}:prepare_site - pH: {ph}, Moisture: {moisture}"],
        "soil_ph": ph,
        "moisture_index": moisture,
        "site_prepared": ph > 5.5 and ph < 8.0,
    }


def sow_seeds(state: State) -> dict[str, Any]:
    """Executes the seed distribution based on site preparation status."""
    if not state.get("site_prepared"):
        return {"log": [f"{UNISPSC_CODE}:sow_seeds - ABORTED: site not prepared"]}

    # Adjust depth based on moisture index
    moisture = state.get("moisture_index", 0.5)
    depth = 40 if moisture > 0.3 else 65
    seeds = 50000

    return {
        "log": [f"{UNISPSC_CODE}:sow_seeds - depth: {depth}mm, count: {seeds}"],
        "planting_depth_mm": depth,
        "seeds_sown": seeds,
    }


def audit_planting(state: State) -> dict[str, Any]:
    """Verifies the planting parameters and emits the final completion report."""
    seeds = state.get("seeds_sown", 0)
    depth = state.get("planting_depth_mm", 0)
    is_valid = seeds > 0 and depth > 0

    return {
        "log": [f"{UNISPSC_CODE}:audit_planting - verified: {is_valid}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "final_depth": depth,
                "total_seeds": seeds,
                "status": "complete" if is_valid else "failed"
            },
            "ok": is_valid,
        },
    }


_g = StateGraph(State)
_g.add_node("prepare_site", prepare_site)
_g.add_node("sow_seeds", sow_seeds)
_g.add_node("audit_planting", audit_planting)

_g.add_edge(START, "prepare_site")
_g.add_edge("prepare_site", "sow_seeds")
_g.add_edge("sow_seeds", "audit_planting")
_g.add_edge("audit_planting", END)

graph = _g.compile()
