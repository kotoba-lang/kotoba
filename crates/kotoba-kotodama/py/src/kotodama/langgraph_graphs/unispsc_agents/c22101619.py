# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101619 — Welding Material (segment 22).

Bespoke graph for managing welding material certification and inventory state.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101619"
UNISPSC_TITLE = "Welding Material"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101619"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    material_grade: str
    batch_certified: bool
    safety_compliance: bool


def validate_specification(state: State) -> dict[str, Any]:
    """Inspects input for material specifications and alloy grades."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "A1-Standard")
    return {
        "log": [f"{UNISPSC_CODE}:validate_specification -> {grade}"],
        "material_grade": grade,
    }


def certify_material(state: State) -> dict[str, Any]:
    """Verifies batch certification and safety data sheet (SDS) availability."""
    grade = state.get("material_grade", "Unknown")
    # Simulation logic: specific grades pass compliance automatically
    is_compliant = "Standard" in grade or grade.startswith("A")
    return {
        "log": [f"{UNISPSC_CODE}:certify_material -> compliant={is_compliant}"],
        "batch_certified": is_compliant,
        "safety_compliance": True,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Generates the final actor result with certification status."""
    is_certified = state.get("batch_certified", False)
    grade = state.get("material_grade", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "CERTIFIED" if is_certified else "PENDING_INSPECTION",
            "grade": grade,
            "ok": is_certified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specification)
_g.add_node("certify", certify_material)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "certify")
_g.add_edge("certify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
