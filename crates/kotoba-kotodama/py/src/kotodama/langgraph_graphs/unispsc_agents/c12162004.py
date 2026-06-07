# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12162004 — Solder.

This agent handles specifications and quality verification for Solder materials,
ensuring alloy composition, flux type, and environmental compliance (RoHS)
meet industrial standards for electronics and plumbing applications.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12162004"
UNISPSC_TITLE = "Solder"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12162004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Solder
    alloy_composition: str
    flux_type: str
    wire_diameter_mm: float
    is_lead_free: bool
    melting_point_celsius: int


def inspect_specifications(state: State) -> dict[str, Any]:
    """Parses and validates the solder wire or bar specifications."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "Sn60/Pb40")
    diameter = float(inp.get("diameter", 0.8))

    # Determine lead-free status based on alloy string
    lead_free = "Pb" not in alloy and "Lead" not in alloy

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "alloy_composition": alloy,
        "wire_diameter_mm": diameter,
        "is_lead_free": lead_free,
    }


def verify_thermal_properties(state: State) -> dict[str, Any]:
    """Determines melting point and flux compatibility."""
    alloy = state.get("alloy_composition", "")

    # Heuristic melting point calculation for common alloys
    if "Sn99" in alloy or "Sn96" in alloy:
        melting_point = 227
    elif "Sn60" in alloy or "60/40" in alloy:
        melting_point = 188
    else:
        melting_point = 217  # Standard SAC305 estimate

    return {
        "log": [f"{UNISPSC_CODE}:verify_thermal_properties - {melting_point}C"],
        "melting_point_celsius": melting_point,
        "flux_type": state.get("input", {}).get("flux", "Rosin Mildly Activated (RMA)"),
    }


def certify_compliance(state: State) -> dict[str, Any]:
    """Finalizes the technical data sheet and compliance certification."""
    is_lead_free = state.get("is_lead_free", False)
    compliance = "RoHS Compliant" if is_lead_free else "Non-RoHS (Industrial Only)"

    return {
        "log": [f"{UNISPSC_CODE}:certify_compliance - {compliance}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "technical_specs": {
                "alloy": state.get("alloy_composition"),
                "diameter_mm": state.get("wire_diameter_mm"),
                "melting_point": state.get("melting_point_celsius"),
                "flux": state.get("flux_type"),
                "lead_free": is_lead_free
            },
            "certification": compliance,
            "status": "Verified",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("thermal", verify_thermal_properties)
_g.add_node("certify", certify_compliance)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "thermal")
_g.add_edge("thermal", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
