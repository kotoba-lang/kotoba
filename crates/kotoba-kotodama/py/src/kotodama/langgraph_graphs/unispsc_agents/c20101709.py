# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101709 — Mining Lubrication (segment 20).

Bespoke logic for managing heavy mining equipment lubrication cycles,
fluid compatibility checks, and maintenance logging.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101709"
UNISPSC_TITLE = "Mining Lubrication"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101709"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Mining Lubrication
    machinery_type: str
    lubricant_grade: str
    viscosity_index: int
    contamination_parts_per_million: float
    inspection_ready: bool


def assess_equipment_spec(state: State) -> dict[str, Any]:
    """Analyzes machinery requirements for specific mining environments."""
    inp = state.get("input") or {}
    machinery = inp.get("machinery", "surface_drill")
    grade = inp.get("required_grade", "ISO-100")

    return {
        "log": [f"{UNISPSC_CODE}:assess_equipment_spec"],
        "machinery_type": machinery,
        "lubricant_grade": grade,
    }


def analyze_fluid_samples(state: State) -> dict[str, Any]:
    """Performs virtual analysis of oil samples for contamination and viscosity."""
    inp = state.get("input") or {}
    ppm = float(inp.get("ppm", 450.0))
    v_index = int(inp.get("viscosity_index", 95))

    # Threshold check for high-pressure mining hydraulic systems
    # If PPM is too high or viscosity is too low, we flag it.
    safe = ppm < 1000.0 and v_index > 80

    return {
        "log": [f"{UNISPSC_CODE}:analyze_fluid_samples"],
        "contamination_parts_per_million": ppm,
        "viscosity_index": v_index,
        "inspection_ready": safe,
    }


def log_lubrication_event(state: State) -> dict[str, Any]:
    """Finalizes the lubrication record for the asset management system."""
    status = "SUCCESS" if state.get("inspection_ready") else "WARNING_HIGH_CONTAMINATION"

    return {
        "log": [f"{UNISPSC_CODE}:log_lubrication_event"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "event_status": status,
            "machinery": state.get("machinery_type"),
            "ok": state.get("inspection_ready", False),
        },
    }


_g = StateGraph(State)

_g.add_node("assess", assess_equipment_spec)
_g.add_node("analyze", analyze_fluid_samples)
_g.add_node("log_event", log_lubrication_event)

_g.add_edge(START, "assess")
_g.add_edge("assess", "analyze")
_g.add_edge("analyze", "log_event")
_g.add_edge("log_event", END)

graph = _g.compile()
