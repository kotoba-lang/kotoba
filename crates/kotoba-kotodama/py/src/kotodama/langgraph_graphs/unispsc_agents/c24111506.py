# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111506"
UNISPSC_TITLE = "Laundry Spec"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    fabric_type: str
    stain_level: str
    wash_temp_c: int
    detergent_ml: float
    cycle_type: str


def analyze_laundry_input(state: State) -> dict[str, Any]:
    """Analyzes input to determine fabric and stain conditions."""
    inp = state.get("input") or {}
    fabric = str(inp.get("fabric", "cotton")).lower()
    stain = str(inp.get("stain", "medium")).lower()

    return {
        "log": [f"{UNISPSC_CODE}:analyze_laundry_input:{fabric}"],
        "fabric_type": fabric,
        "stain_level": stain,
    }


def determine_treatment(state: State) -> dict[str, Any]:
    """Calculates wash parameters based on fabric and stain analysis."""
    fabric = state.get("fabric_type", "cotton")
    stain = state.get("stain_level", "medium")

    # Select temperature based on fabric sensitivity
    if fabric in ["silk", "wool", "delicate"]:
        temp = 30
        cycle = "gentle"
    elif fabric in ["synthetic", "blend"]:
        temp = 40
        cycle = "permanent_press"
    else:
        temp = 60
        cycle = "heavy_duty" if stain == "high" else "normal"

    # Calculate detergent volume
    base_ml = 50.0
    if stain == "high":
        base_ml *= 1.4
    elif stain == "low":
        base_ml *= 0.8

    return {
        "log": [f"{UNISPSC_CODE}:determine_treatment:{temp}C:{cycle}"],
        "wash_temp_c": temp,
        "detergent_ml": base_ml,
        "cycle_type": cycle
    }


def compile_specification(state: State) -> dict[str, Any]:
    """Generates the final laundry specification output."""
    return {
        "log": [f"{UNISPSC_CODE}:compile_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "target_fabric": state.get("fabric_type"),
                "recommended_temp_c": state.get("wash_temp_c"),
                "detergent_dosage_ml": state.get("detergent_ml"),
                "wash_cycle": state.get("cycle_type"),
                "stain_intensity": state.get("stain_level")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_laundry_input)
_g.add_node("treat", determine_treatment)
_g.add_node("emit", compile_specification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "treat")
_g.add_edge("treat", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
