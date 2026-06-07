# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26121505"
UNISPSC_TITLE = "Wire Spec"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26121505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    conductor_material: str
    gauge_awg: int
    voltage_max: int
    is_compliant: bool


def analyze_physical_properties(state: State) -> dict[str, Any]:
    """Analyzes the physical characteristics of the wire specification."""
    inp = state.get("input") or {}
    material = inp.get("material", "copper")
    gauge = inp.get("gauge", 14)
    return {
        "log": [f"{UNISPSC_CODE}:analyze_physical_properties"],
        "conductor_material": material,
        "gauge_awg": gauge,
    }


def evaluate_electrical_limits(state: State) -> dict[str, Any]:
    """Evaluates the electrical capacity and safety margins based on gauge and material."""
    inp = state.get("input") or {}
    voltage = inp.get("voltage", 600)
    # Simple compliance logic for wire specifications
    material = state.get("conductor_material", "unknown")
    gauge = state.get("gauge_awg", 0)

    # Example rule: Copper wire between 10 and 24 AWG is standard compliance
    is_compliant = material.lower() == "copper" and 10 <= gauge <= 24

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_electrical_limits"],
        "voltage_max": voltage,
        "is_compliant": is_compliant,
    }


def generate_certification(state: State) -> dict[str, Any]:
    """Finalizes the wire specification and generates the result record."""
    is_compliant = state.get("is_compliant", False)
    return {
        "log": [f"{UNISPSC_CODE}:generate_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specification": {
                "material": state.get("conductor_material"),
                "gauge_awg": state.get("gauge_awg"),
                "voltage_rating_max": state.get("voltage_max"),
            },
            "status": "certified" if is_compliant else "pending_review",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_physical_properties)
_g.add_node("evaluate", evaluate_electrical_limits)
_g.add_node("finalize", generate_certification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
