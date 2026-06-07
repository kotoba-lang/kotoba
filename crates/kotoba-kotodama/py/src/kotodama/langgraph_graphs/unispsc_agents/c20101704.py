# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20101704 — Relay Spec (segment 20).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20101704"
UNISPSC_TITLE = "Relay Spec"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20101704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain state for Relay Spec (Mining & Drilling context)
    nominal_voltage: float
    contact_arrangement: str
    is_explosion_proof: bool
    ip_rating: str
    compliance_check: bool


def extract_parameters(state: State) -> dict[str, Any]:
    """Parses input for basic relay electrical specifications."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 24.0))
    contacts = str(inp.get("contacts", "DPDT"))

    return {
        "log": [f"{UNISPSC_CODE}:extract_parameters"],
        "nominal_voltage": voltage,
        "contact_arrangement": contacts,
    }


def analyze_environmental_fit(state: State) -> dict[str, Any]:
    """Determines safety ratings based on the application environment."""
    inp = state.get("input") or {}
    # Segment 20 context: Mining and Well Drilling
    is_hazardous = inp.get("hazardous_area", False) or inp.get("methane_risk", False)
    depth = float(inp.get("well_depth", 0.0))

    # Deep wells or hazardous areas require explosion proofing
    ex_required = is_hazardous or depth > 500.0
    ip = "IP68" if depth > 10.0 else "IP54"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_environmental_fit"],
        "is_explosion_proof": ex_required,
        "ip_rating": ip,
    }


def certify_specification(state: State) -> dict[str, Any]:
    """Finalizes the technical specification and verifies safety compliance."""
    voltage = state.get("nominal_voltage", 0.0)
    is_ex = state.get("is_explosion_proof", False)

    # Safety rule: High voltage in hazardous drilling areas must be Ex certified
    is_safe = not (voltage > 110.0 and is_ex)

    return {
        "log": [f"{UNISPSC_CODE}:certify_specification"],
        "compliance_check": is_safe,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_safe,
            "specification": {
                "voltage": voltage,
                "contacts": state.get("contact_arrangement"),
                "ex_proof": is_ex,
                "ip_rating": state.get("ip_rating"),
                "safety_certified": is_safe
            }
        },
    }


_g = StateGraph(State)
_g.add_node("extract", extract_parameters)
_g.add_node("analyze", analyze_environmental_fit)
_g.add_node("certify", certify_specification)

_g.add_edge(START, "extract")
_g.add_edge("extract", "analyze")
_g.add_edge("analyze", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
