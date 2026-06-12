# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20140000 — Mining (segment 20).

Bespoke graph logic for mining operations, including site prospecting,
resource extraction simulation, and yield assaying.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20140000"
UNISPSC_TITLE = "Mining"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20140000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Mining
    site_coordinates: str
    ore_concentration: float
    environmental_safety_index: float
    extraction_ready: bool


def survey(state: State) -> dict[str, Any]:
    """Surveys the mining site and evaluates environmental safety."""
    inp = state.get("input") or {}
    coords = inp.get("coordinates", "0.0,0.0")
    safety_idx = inp.get("safety_score", 0.98)

    return {
        "log": [f"{UNISPSC_CODE}:survey -> site {coords} evaluated"],
        "site_coordinates": coords,
        "environmental_safety_index": safety_idx,
        "extraction_ready": safety_idx > 0.7,
    }


def excavate(state: State) -> dict[str, Any]:
    """Simulates the extraction phase based on site readiness."""
    is_ready = state.get("extraction_ready", False)
    concentration = 0.0

    if is_ready:
        concentration = 0.42  # Simulating a specific ore grade
        log_msg = f"{UNISPSC_CODE}:excavate -> extraction successful at {concentration}"
    else:
        log_msg = f"{UNISPSC_CODE}:excavate -> extraction aborted: safety threshold"

    return {
        "log": [log_msg],
        "ore_concentration": concentration,
    }


def refine(state: State) -> dict[str, Any]:
    """Processes the raw ore concentration into a final result."""
    conc = state.get("ore_concentration", 0.0)
    coords = state.get("site_coordinates", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:refine -> final assay completed"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "site": coords,
            "purity": conc * 0.95,
            "status": "commercial_grade" if conc > 0.3 else "low_yield",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("survey", survey)
_g.add_node("excavate", excavate)
_g.add_node("refine", refine)

_g.add_edge(START, "survey")
_g.add_edge("survey", "excavate")
_g.add_edge("excavate", "refine")
_g.add_edge("refine", END)

graph = _g.compile()
