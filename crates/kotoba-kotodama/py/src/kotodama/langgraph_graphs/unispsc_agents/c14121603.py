# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121603"
UNISPSC_TITLE = "Paper Tube"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Paper Tube domain state
    dimensions: dict[str, float]
    wall_thickness: float
    material_grade: str
    is_heavy_duty: bool


def ingest_specs(state: State) -> dict[str, Any]:
    """Parse and validate paper tube dimensions and materials."""
    inp = state.get("input") or {}
    params = inp.get("parameters", {})

    # Extract dimensions or provide industrial defaults
    diam = params.get("diameter", 2.0)
    length = params.get("length", 24.0)
    thick = params.get("thickness", 0.1)

    return {
        "log": [f"{UNISPSC_CODE}:ingest_specs"],
        "dimensions": {
            "inner_diameter": diam,
            "outer_diameter": diam + (2 * thick),
            "length": length
        },
        "wall_thickness": thick,
        "material_grade": params.get("grade", "Industrial")
    }


def analyze_durability(state: State) -> dict[str, Any]:
    """Evaluate if the tube meets heavy-duty thresholds for structural use."""
    thick = state.get("wall_thickness", 0.0)
    grade = state.get("material_grade", "")

    # Logic: Heavy duty if wall is thick or material is premium
    is_heavy = thick >= 0.2 or grade.lower() in ["heavy", "premium"]

    return {
        "log": [f"{UNISPSC_CODE}:analyze_durability"],
        "is_heavy_duty": is_heavy
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalize the paper tube actor result with metadata and certifications."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": state.get("dimensions"),
            "is_heavy_duty": state.get("is_heavy_duty"),
            "material_grade": state.get("material_grade"),
            "status": "specification_certified"
        }
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_specs)
_g.add_node("analyze", analyze_durability)
_g.add_node("finalize", finalize_asset)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
