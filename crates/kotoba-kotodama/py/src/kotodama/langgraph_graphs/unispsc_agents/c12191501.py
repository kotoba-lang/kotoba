# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12191501 — Carbon Black (segment 12).

Bespoke graph logic for Carbon Black material characterization and grading.
This implementation handles state transitions for physical property analysis,
ASTM grade verification, and manifest generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12191501"
UNISPSC_TITLE = "Carbon Black"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12191501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    iodine_adsorption_number: float
    oil_absorption_number: float
    purity_level: float
    astm_grade: str
    is_compliant: bool


def characterize_material(state: State) -> dict[str, Any]:
    """Extract and characterize the physical properties of the carbon black."""
    inp = state.get("input") or {}
    iodine = float(inp.get("iodine_no", 82.0))
    oan = float(inp.get("oan", 102.0))

    return {
        "log": [f"{UNISPSC_CODE}:characterize_material"],
        "iodine_adsorption_number": iodine,
        "oil_absorption_number": oan,
    }


def evaluate_purity_and_grade(state: State) -> dict[str, Any]:
    """Verify purity level and assign a corresponding ASTM grade."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity", 0.99))

    iodine = state.get("iodine_adsorption_number", 0.0)
    # Simple logic to determine N-series grade
    if iodine > 120:
        grade = "N110"
    elif iodine > 80:
        grade = "N330"
    else:
        grade = "N660"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_purity_and_grade"],
        "purity_level": purity,
        "astm_grade": grade,
        "is_compliant": purity > 0.985,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generate the final result manifest for the Carbon Black agent."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "properties": {
                "astm_grade": state.get("astm_grade"),
                "iodine_no": state.get("iodine_adsorption_number"),
                "oan": state.get("oil_absorption_number"),
                "purity": state.get("purity_level"),
            },
            "status": "APPROVED" if state.get("is_compliant") else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("characterize", characterize_material)
_g.add_node("evaluate", evaluate_purity_and_grade)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "characterize")
_g.add_edge("characterize", "evaluate")
_g.add_edge("evaluate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
