# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151519 — Excavator (segment 10).

This module implements bespoke logic for simulating excavation operations,
managing site survey data, and tracking material movement.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151519"
UNISPSC_TITLE = "Excavator"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151519"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific excavator fields
    site_id: str
    soil_type: str
    excavation_depth_meters: float
    bucket_cycles: int
    safety_clearance_granted: bool


def survey_site(state: State) -> dict[str, Any]:
    """Inspects the job site and prepares the machine parameters."""
    inp = state.get("input") or {}
    site_id = inp.get("site_id", "SITE-UNKNOWN")
    soil = inp.get("soil_type", "clay")

    return {
        "log": [f"{UNISPSC_CODE}:survey_site -> {site_id} ({soil})"],
        "site_id": site_id,
        "soil_type": soil,
        "safety_clearance_granted": True if site_id != "SITE-UNKNOWN" else False
    }


def excavate_material(state: State) -> dict[str, Any]:
    """Simulates the physical digging process based on input cycles."""
    if not state.get("safety_clearance_granted"):
        return {"log": [f"{UNISPSC_CODE}:excavate_material -> ABORTED (No Safety Clearance)"]}

    inp = state.get("input") or {}
    cycles = inp.get("cycles", 10)
    target_depth = inp.get("depth", 1.5)

    return {
        "log": [f"{UNISPSC_CODE}:excavate_material -> {cycles} cycles at {target_depth}m"],
        "bucket_cycles": cycles,
        "excavation_depth_meters": target_depth
    }


def complete_job(state: State) -> dict[str, Any]:
    """Finalizes the work order and emits the result report."""
    is_ok = state.get("safety_clearance_granted", False)

    return {
        "log": [f"{UNISPSC_CODE}:complete_job"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "summary": {
                "site": state.get("site_id"),
                "soil": state.get("soil_type"),
                "cycles_completed": state.get("bucket_cycles", 0),
                "depth_reached": state.get("excavation_depth_meters", 0.0)
            },
            "ok": is_ok
        }
    }


_g = StateGraph(State)

_g.add_node("survey_site", survey_site)
_g.add_node("excavate_material", excavate_material)
_g.add_node("complete_job", complete_job)

_g.add_edge(START, "survey_site")
_g.add_edge("survey_site", "excavate_material")
_g.add_edge("excavate_material", "complete_job")
_g.add_edge("complete_job", END)

graph = _g.compile()
