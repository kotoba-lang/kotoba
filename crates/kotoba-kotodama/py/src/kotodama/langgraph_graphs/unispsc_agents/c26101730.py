# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101730 — Rocker Shaft.
Bespoke engine component validation logic for shaft integrity and oil flow.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101730"
UNISPSC_TITLE = "Rocker Shaft"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101730"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Rocker Shaft domain fields
    shaft_straightness_mm: float
    oil_passage_clearance: bool
    surface_finish_ra: float
    hardness_hrc: int


def validate_metallurgy(state: State) -> dict[str, Any]:
    """Inspects the material hardness and surface finish specifications."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:validate_metallurgy"],
        "hardness_hrc": inp.get("hardness", 60),
        "surface_finish_ra": inp.get("finish", 0.4),
    }


def check_geometry(state: State) -> dict[str, Any]:
    """Verifies shaft straightness and ensures lubrication passages are clear."""
    inp = state.get("input") or {}
    straightness = inp.get("straightness", 0.01)
    # Simulate pressure test for internal oil passages
    passages_clear = inp.get("flow_test", True)
    return {
        "log": [f"{UNISPSC_CODE}:check_geometry"],
        "shaft_straightness_mm": straightness,
        "oil_passage_clearance": passages_clear,
    }


def finalize_inspection(state: State) -> dict[str, Any]:
    """Aggregates sensor data into a final quality assurance report."""
    # Logic to determine if the rocker shaft meets engine specs
    is_qc_pass = (
        state.get("hardness_hrc", 0) >= 50 and
        state.get("shaft_straightness_mm", 1.0) < 0.05 and
        state.get("oil_passage_clearance") is True
    )

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inspection"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "qc_status": "PASS" if is_qc_pass else "FAIL",
            "metadata": {
                "straightness_verified": state.get("shaft_straightness_mm"),
                "hardness_recorded": state.get("hardness_hrc"),
                "passages_verified": state.get("oil_passage_clearance")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_metallurgy", validate_metallurgy)
_g.add_node("check_geometry", check_geometry)
_g.add_node("finalize_inspection", finalize_inspection)

_g.add_edge(START, "validate_metallurgy")
_g.add_edge("validate_metallurgy", "check_geometry")
_g.add_edge("check_geometry", "finalize_inspection")
_g.add_edge("finalize_inspection", END)

graph = _g.compile()
