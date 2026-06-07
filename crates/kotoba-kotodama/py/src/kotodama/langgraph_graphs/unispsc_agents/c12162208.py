# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Bespoke LangGraph agent for UNISPSC 12162208: Ceramic.
Focuses on material composition validation and firing specification processing.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162208"
UNISPSC_TITLE = "Ceramic"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162208"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Ceramic
    composition: dict[str, float]
    firing_temp_c: int
    kiln_duration_min: int
    is_porous: bool


def inspect_composition(state: State) -> dict[str, Any]:
    """Inspects the raw material composition for ceramic production."""
    inp = state.get("input") or {}
    comp = inp.get("composition", {"clay": 0.7, "feldspar": 0.2, "quartz": 0.1})

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition"],
        "composition": comp,
        "is_porous": comp.get("clay", 0.0) > 0.5
    }


def calculate_firing_parameters(state: State) -> dict[str, Any]:
    """Determines optimal firing temperature based on material composition."""
    comp = state.get("composition") or {}
    clay_content = comp.get("clay", 0.0)

    # Logic to determine temperature based on clay content
    # Higher clay content often requires higher firing temperatures (Stoneware/Porcelain)
    temp = 1250 if clay_content > 0.6 else 1050
    duration = 600 if temp > 1100 else 420

    return {
        "log": [f"{UNISPSC_CODE}:calculate_firing_parameters"],
        "firing_temp_c": temp,
        "kiln_duration_min": duration
    }


def record_ceramic_batch(state: State) -> dict[str, Any]:
    """Records the finalized ceramic batch details and specifications."""
    return {
        "log": [f"{UNISPSC_CODE}:record_ceramic_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "firing_temperature": state.get("firing_temp_c"),
                "duration_minutes": state.get("kiln_duration_min"),
                "porosity_flag": state.get("is_porous")
            },
            "status": "batch_certified"
        }
    }


_g = StateGraph(State)
_g.add_node("inspect_composition", inspect_composition)
_g.add_node("calculate_firing_parameters", calculate_firing_parameters)
_g.add_node("record_ceramic_batch", record_ceramic_batch)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "calculate_firing_parameters")
_g.add_edge("calculate_firing_parameters", "record_ceramic_batch")
_g.add_edge("record_ceramic_batch", END)

graph = _g.compile()
