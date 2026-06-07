# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11131607 — Ceramic (segment 11).

Bespoke graph logic for ceramic material processing, including raw material
inspection, kiln firing simulation, and surface finishing validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11131607"
UNISPSC_TITLE = "Ceramic"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11131607"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Ceramic
    clay_body_type: str
    firing_temp_celsius: int
    glaze_viscosity: float
    vitrification_status: str


def inspect_raw_materials(state: State) -> dict[str, Any]:
    """Validate the composition of the clay body and set firing targets."""
    inp = state.get("input") or {}
    clay = inp.get("clay", "porcelain")
    temp = inp.get("target_temp", 1280)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_materials"],
        "clay_body_type": clay,
        "firing_temp_celsius": temp,
        "vitrification_status": "raw",
    }


def kiln_firing_process(state: State) -> dict[str, Any]:
    """Simulate the heat-work cycle and determine vitrification level."""
    temp = state.get("firing_temp_celsius", 0)

    # Simple logic to simulate ceramic transformation
    status = "bisque"
    if temp >= 1200:
        status = "vitrified"
    elif temp > 1000:
        status = "earthenware"

    return {
        "log": [f"{UNISPSC_CODE}:kiln_firing_process"],
        "vitrification_status": status,
        "glaze_viscosity": max(0.1, 1500.0 - temp),
    }


def surface_finishing(state: State) -> dict[str, Any]:
    """Apply surface treatment and finalize the product manifest."""
    v_status = state.get("vitrification_status")
    clay = state.get("clay_body_type")

    return {
        "log": [f"{UNISPSC_CODE}:surface_finishing"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ceramic_specs": {
                "body": clay,
                "status": v_status,
                "viscosity_index": state.get("glaze_viscosity"),
            },
            "quality_certified": v_status != "raw",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_raw_materials)
_g.add_node("fire", kiln_firing_process)
_g.add_node("finish", surface_finishing)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "fire")
_g.add_edge("fire", "finish")
_g.add_edge("finish", END)

graph = _g.compile()
