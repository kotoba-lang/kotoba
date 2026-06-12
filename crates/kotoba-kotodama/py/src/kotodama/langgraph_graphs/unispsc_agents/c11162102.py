# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11162102 — Magnesium (segment 11).

Bespoke graph logic for magnesium extraction and refining workflows.
This agent handles purity verification, form factor classification,
and safety compliance for metallic magnesium and its alloys.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11162102"
UNISPSC_TITLE = "Magnesium"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11162102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    purity_percentage: float
    form_factor: str  # e.g., Ingot, Powder, Turnings
    alloy_grade: str  # e.g., AZ91D, AM60B
    is_flammable_solid: bool


def assay_ore(state: State) -> dict[str, Any]:
    """Analyze input specifications to determine initial magnesium content."""
    inp = state.get("input") or {}
    purity = float(inp.get("target_purity", 99.8))
    source = inp.get("source_material", "Dolomite")

    return {
        "log": [f"{UNISPSC_CODE}:assay_ore: {source} analysis complete"],
        "purity_percentage": purity,
    }


def refinement_process(state: State) -> dict[str, Any]:
    """Simulate the Pidgeon process or Electrolytic reduction."""
    purity = state.get("purity_percentage", 0.0)
    # Magnesium is highly reactive; form factor affects safety protocols
    form = state.get("input", {}).get("requested_form", "Ingot")

    is_dangerous = form.lower() in ["powder", "turnings", "ribbon"]

    return {
        "log": [f"{UNISPSC_CODE}:refinement_process: casting into {form}"],
        "form_factor": form,
        "is_flammable_solid": is_dangerous,
        "alloy_grade": "Pure Mg" if purity > 99.9 else "Standard Grade",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Final quality check and safety documentation generation."""
    is_safe_to_ship = not state.get("is_flammable_solid", False)
    grade = state.get("alloy_grade", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance: {grade} verified"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "Certified",
            "purity": f"{state.get('purity_percentage')}%",
            "hazmat_required": not is_safe_to_ship,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("assay_ore", assay_ore)
_g.add_node("refinement_process", refinement_process)
_g.add_node("verify_compliance", verify_compliance)

_g.add_edge(START, "assay_ore")
_g.add_edge("assay_ore", "refinement_process")
_g.add_edge("refinement_process", "verify_compliance")
_g.add_edge("verify_compliance", END)

graph = _g.compile()
