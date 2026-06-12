# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242604 — Lapping (segment 23).
Bespoke logic for precision surface finishing processes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242604"
UNISPSC_TITLE = "Lapping"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242604"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Lapping-specific domain fields
    target_roughness_ra: float
    current_roughness_ra: float
    abrasive_grit_size: int
    lap_plate_speed_rpm: int
    coolant_flow_rate_lpm: float


def initialize_lapping_setup(state: State) -> dict[str, Any]:
    """Calculates optimal lapping parameters based on input surface finish requirements."""
    inp = state.get("input") or {}
    requested_ra = float(inp.get("target_ra", 0.05))

    # Determine abrasive grit based on precision requirements
    grit = 1500 if requested_ra < 0.1 else 800

    return {
        "log": [f"{UNISPSC_CODE}:initialize_lapping_setup(target={requested_ra})"],
        "target_roughness_ra": requested_ra,
        "current_roughness_ra": 1.5,  # Nominal starting roughness for pre-lapped part
        "abrasive_grit_size": grit,
        "lap_plate_speed_rpm": 60,
        "coolant_flow_rate_lpm": 2.5,
    }


def execute_abrasive_cycle(state: State) -> dict[str, Any]:
    """Simulates the physical material removal process using abrasive slurry."""
    grit = state.get("abrasive_grit_size", 800)
    current_ra = state.get("current_roughness_ra", 1.5)
    speed = state.get("lap_plate_speed_rpm", 60)

    # Material removal simulation based on grit and speed efficiency
    efficiency = (grit / 1000.0) * (speed / 60.0)
    reduction = 0.5 * efficiency
    new_ra = max(0.01, current_ra - reduction)

    return {
        "log": [f"{UNISPSC_CODE}:execute_abrasive_cycle(new_ra={new_ra:.3f})"],
        "current_roughness_ra": new_ra,
    }


def validate_finish_quality(state: State) -> dict[str, Any]:
    """Performs final metrology inspection to ensure finish meets specifications."""
    current_ra = state.get("current_roughness_ra", 1.5)
    target_ra = state.get("target_roughness_ra", 0.05)

    # Allow for a small manufacturing tolerance band
    within_spec = current_ra <= (target_ra + 0.005)

    return {
        "log": [f"{UNISPSC_CODE}:validate_finish_quality(ok={within_spec})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "inspection_data": {
                "final_ra": round(current_ra, 4),
                "grit_used": state.get("abrasive_grit_size"),
                "status": "ACCEPTED" if within_spec else "OUT_OF_SPEC",
            },
            "ok": within_spec,
        },
    }


_g = StateGraph(State)
_g.add_node("setup", initialize_lapping_setup)
_g.add_node("process", execute_abrasive_cycle)
_g.add_node("validate", validate_finish_quality)

_g.add_edge(START, "setup")
_g.add_edge("setup", "process")
_g.add_edge("process", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
