# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251506 — Pipe (segment 23).

This bespoke implementation handles state transitions for piping specifications,
verifying material integrity, pressure ratings, and compliance with industrial
standards for fluid transport.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251506"
UNISPSC_TITLE = "Pipe"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke Pipe domain fields
    material: str
    diameter_mm: float
    pressure_rating_psi: int
    is_compliant: bool
    inspection_id: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the physical dimensions and material composition of the pipe."""
    inp = state.get("input") or {}
    material = inp.get("material", "Unknown")
    diameter = float(inp.get("diameter_mm", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "material": material,
        "diameter_mm": diameter,
        "is_compliant": diameter > 0 and material != "Unknown"
    }


def analyze_pressure_tolerance(state: State) -> dict[str, Any]:
    """Calculates if the pipe can handle the specified load/pressure."""
    inp = state.get("input") or {}
    req_pressure = int(inp.get("required_pressure_psi", 0))

    # Simple logic: PVC has lower threshold than Steel
    material = state.get("material", "")
    max_safe = 5000 if material.lower() == "steel" else 200

    safe = req_pressure <= max_safe
    return {
        "log": [f"{UNISPSC_CODE}:analyze_pressure_tolerance"],
        "pressure_rating_psi": req_pressure,
        "is_compliant": state.get("is_compliant", False) and safe,
        "inspection_id": f"INSP-{UNISPSC_CODE}-{hash(material) % 10000}"
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Finalizes the pipe actor result and emits compliance status."""
    is_ok = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": is_ok,
            "inspection_reference": state.get("inspection_id"),
            "metadata": {
                "material": state.get("material"),
                "diameter": state.get("diameter_mm"),
                "pressure_limit": state.get("pressure_rating_psi")
            }
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("analyze", analyze_pressure_tolerance)
_g.add_node("emit", certify_and_emit)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
