# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23271803 — Solder (segment 23).

Bespoke graph logic for soldering materials and metallurgical verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271803"
UNISPSC_TITLE = "Solder"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Solder processing
    alloy_composition: str
    melting_point_c: float
    flux_type: str
    diameter_mm: float
    safety_compliance: bool


def inspect_composition(state: State) -> dict[str, Any]:
    """Inspects the alloy composition and diameter from input specs."""
    inp = state.get("input") or {}
    alloy = str(inp.get("alloy", "Sn63Pb37"))
    diam = float(inp.get("diameter", 0.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_composition -> {alloy} @ {diam}mm"],
        "alloy_composition": alloy,
        "diameter_mm": diam,
    }


def thermal_calibration(state: State) -> dict[str, Any]:
    """Determines melting point and assigns flux properties based on alloy."""
    alloy = state.get("alloy_composition", "")

    # Representative data for common solder alloys
    metallurgy = {
        "Sn63Pb37": (183.0, "RMA"),
        "Sn60Pb40": (190.0, "RMA"),
        "Sn96.5Ag3.0Cu0.5": (217.0, "No-Clean"),
    }

    temp, flux = metallurgy.get(alloy, (200.0, "Rosin"))

    return {
        "log": [f"{UNISPSC_CODE}:thermal_calibration -> MP: {temp}C, Flux: {flux}"],
        "melting_point_c": temp,
        "flux_type": flux,
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Certifies the solder batch and prepares the final result."""
    alloy = state.get("alloy_composition")
    temp = state.get("melting_point_c")

    is_compliant = alloy is not None and temp is not None

    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification -> compliance: {is_compliant}"],
        "safety_compliance": is_compliant,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "alloy": alloy,
            "melting_point": temp,
            "flux": state.get("flux_type"),
            "status": "certified" if is_compliant else "rejected",
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_composition", inspect_composition)
_g.add_node("thermal_calibration", thermal_calibration)
_g.add_node("finalize_specification", finalize_specification)

_g.add_edge(START, "inspect_composition")
_g.add_edge("inspect_composition", "thermal_calibration")
_g.add_edge("thermal_calibration", "finalize_specification")
_g.add_edge("finalize_specification", END)

graph = _g.compile()
