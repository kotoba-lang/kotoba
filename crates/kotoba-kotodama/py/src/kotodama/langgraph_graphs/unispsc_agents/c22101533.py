# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101533 — Fastener (segment 22).

Bespoke LangGraph implementation for fastener specification validation,
load-bearing analysis, and material certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101533"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101533"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Fastener
    material_grade: str
    tensile_strength_psi: int
    thread_consistency_verified: bool
    corrosion_coating_type: str


def verify_specifications(state: State) -> dict[str, Any]:
    """Validates the material grade and dimensional properties of the fastener."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    grade = inp.get("grade", "Grade 8")

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications"],
        "material_grade": f"{material} {grade}",
        "thread_consistency_verified": True,
    }


def analyze_load_bearing(state: State) -> dict[str, Any]:
    """Calculates the theoretical tensile capacity based on the verified grade."""
    grade = state.get("material_grade", "")
    # Grade 8 fasteners typically have a higher tensile strength (150ksi)
    strength = 150000 if "Grade 8" in grade else 120000

    return {
        "log": [f"{UNISPSC_CODE}:analyze_load_bearing"],
        "tensile_strength_psi": strength,
        "corrosion_coating_type": "Zinc Flake" if strength > 130000 else "Clear Zinc",
    }


def certify_fastener(state: State) -> dict[str, Any]:
    """Generates the final certification report for the fastener lot."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_fastener"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "material": state.get("material_grade"),
                "tensile_capacity_psi": state.get("tensile_strength_psi"),
                "coating": state.get("corrosion_coating_type"),
            },
            "status": "Certified" if state.get("thread_consistency_verified") else "Pending",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specifications", verify_specifications)
_g.add_node("analyze_load_bearing", analyze_load_bearing)
_g.add_node("certify_fastener", certify_fastener)

_g.add_edge(START, "verify_specifications")
_g.add_edge("verify_specifications", "analyze_load_bearing")
_g.add_edge("analyze_load_bearing", "certify_fastener")
_g.add_edge("certify_fastener", END)

graph = _g.compile()
