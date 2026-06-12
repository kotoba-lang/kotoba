# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25161509 — Bike Specs (segment 25).

Bespoke logic for validating and processing bicycle technical specifications,
ensuring component compatibility and safety standard compliance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25161509"
UNISPSC_TITLE = "Bike Specs"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25161509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Bike Specs
    frame_material: str
    wheel_diameter_mm: int
    braking_system: str
    is_safety_certified: bool


def ingest_specifications(state: State) -> dict[str, Any]:
    """Parses raw input into structured bike specification components."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:ingest_specifications"],
        "frame_material": inp.get("frame", "Alloy"),
        "wheel_diameter_mm": int(inp.get("wheels", 622)),
        "braking_system": inp.get("brakes", "Disc"),
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks the bike specs against industry safety regulations."""
    # Simulation: Carbon frames must have specific certification flags
    material = state.get("frame_material", "Alloy")
    is_valid = True
    if material.lower() == "carbon" and "cert" not in state.get("input", {}):
        is_valid = False

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "is_safety_certified": is_valid,
    }


def export_technical_sheet(state: State) -> dict[str, Any]:
    """Generates the final technical data sheet for the specified bike."""
    success = state.get("is_safety_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:export_technical_sheet"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "spec_summary": {
                "frame": state.get("frame_material"),
                "wheels": f"{state.get('wheel_diameter_mm')}mm",
                "brakes": state.get("braking_system")
            },
            "status": "APPROVED" if success else "PENDING_CERTIFICATION",
            "segment": UNISPSC_SEGMENT
        },
    }


_g = StateGraph(State)

_g.add_node("ingest", ingest_specifications)
_g.add_node("verify", verify_compliance)
_g.add_node("export", export_technical_sheet)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "verify")
_g.add_edge("verify", "export")
_g.add_edge("export", END)

graph = _g.compile()
