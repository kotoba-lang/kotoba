# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122315 — Fastener (segment 20).

Bespoke graph logic for industrial fasteners, handling specification validation,
mechanical property verification, and quality certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122315"
UNISPSC_TITLE = "Fastener"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122315"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain-specific fields for Fasteners
    material_grade: str
    tensile_strength_psi: int
    thread_type: str
    coating_integrity_verified: bool
    batch_compliant: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates the physical and material specifications of the fastener."""
    inp = state.get("input") or {}
    material = inp.get("material", "Grade 5 Steel")
    thread = inp.get("thread", "UNC-2A")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "material_grade": material,
        "thread_type": thread,
        "batch_compliant": True if material and thread else False
    }


def verify_mechanical_properties(state: State) -> dict[str, Any]:
    """Simulates testing for tensile strength and coating resistance."""
    # Logic based on material grade
    grade = state.get("material_grade", "")
    strength = 120000 if "Grade 5" in grade else 150000

    return {
        "log": [f"{UNISPSC_CODE}:verify_mechanical_properties"],
        "tensile_strength_psi": strength,
        "coating_integrity_verified": True
    }


def certify_fastener(state: State) -> dict[str, Any]:
    """Generates the final certificate of compliance for the fastener batch."""
    is_ok = state.get("batch_compliant", False) and state.get("coating_integrity_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_fastener"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material_grade"),
                "tensile_strength": f"{state.get('tensile_strength_psi')} PSI",
                "threads": state.get("thread_type")
            },
            "certified": is_ok,
            "status": "APPROVED" if is_ok else "REJECTED"
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("verify_mechanical_properties", verify_mechanical_properties)
_g.add_node("certify_fastener", certify_fastener)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "verify_mechanical_properties")
_g.add_edge("verify_mechanical_properties", "certify_fastener")
_g.add_edge("certify_fastener", END)

graph = _g.compile()
