# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13111210"
UNISPSC_TITLE = "Mineral"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13111210"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    extraction_site: str
    ore_grade: float
    chemical_formula: str
    moisture_content: float
    is_industrial_grade: bool


def inspect_raw_material(state: State) -> dict[str, Any]:
    """Inspects the raw mineral input and identifies origin and basic chemistry."""
    inp = state.get("input") or {}
    formula = inp.get("formula", "SiO2")
    return {
        "log": [f"{UNISPSC_CODE}:inspect_raw_material"],
        "extraction_site": inp.get("site", "Central Basin Quarry"),
        "chemical_formula": formula,
        "is_industrial_grade": len(formula) > 2,
    }


def analyze_purity(state: State) -> dict[str, Any]:
    """Calculates the refined ore grade based on moisture and input purity."""
    inp = state.get("input") or {}
    raw_p = inp.get("purity", 0.85)
    moisture = inp.get("moisture", 0.02)
    # Refinement logic: lower moisture usually implies higher concentrated grade
    refined_grade = raw_p * (1.0 - (moisture * 0.5))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_purity"],
        "ore_grade": round(refined_grade, 4),
        "moisture_content": moisture,
    }


def finalize_mineral_manifest(state: State) -> dict[str, Any]:
    """Generates the final certificate and manifest for the mineral lot."""
    is_industrial = state.get("is_industrial_grade", False)
    grade = state.get("ore_grade", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_mineral_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "manifest": {
                "site": state.get("extraction_site"),
                "formula": state.get("chemical_formula"),
                "purity_index": grade,
                "classification": "Industrial" if is_industrial else "Standard",
            },
            "certified": grade > 0.7,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_raw_material)
_g.add_node("analyze", analyze_purity)
_g.add_node("finalize", finalize_mineral_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
