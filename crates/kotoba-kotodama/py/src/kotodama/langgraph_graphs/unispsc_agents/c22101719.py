# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101719 — Steel (segment 22).

Bespoke graph logic for steel procurement and quality assurance.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101719"
UNISPSC_TITLE = "Steel"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101719"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    alloy_grade: str
    tensile_strength_mpa: int
    dimensions_mm: dict[str, float]
    quality_certified: bool
    batch_tracking_id: str


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspects the incoming steel requirements and maps alloy grades."""
    inp = state.get("input") or {}
    alloy = inp.get("alloy", "ASTM A36")
    dims = inp.get("dimensions", {"thickness": 10.0, "width": 1500.0})

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "alloy_grade": alloy,
        "dimensions_mm": dims,
        "batch_tracking_id": f"STL-{alloy.replace(' ', '-')}-2026",
    }


def verify_structural_integrity(state: State) -> dict[str, Any]:
    """Simulates metallurgical testing for tensile strength and carbon content."""
    grade = state.get("alloy_grade", "Standard")
    # Simulate a strength value based on grade
    strength = 450 if "A36" in grade else 250

    return {
        "log": [f"{UNISPSC_CODE}:verify_structural_integrity"],
        "tensile_strength_mpa": strength,
        "quality_certified": strength >= 250,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Prepares the final actor result for construction logistics."""
    certified = state.get("quality_certified", False)
    tracking = state.get("batch_tracking_id", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": certified,
            "tracking_id": tracking,
            "spec": {
                "alloy": state.get("alloy_grade"),
                "strength": f"{state.get('tensile_strength_mpa')} MPa",
            },
            "status": "Ready for Dispatch" if certified else "Hold - Quality Issue",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("verify", verify_structural_integrity)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
