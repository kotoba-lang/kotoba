# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101904 — Engine Part (segment 26).

Bespoke graph logic for Engine Part components. This agent handles
specification verification, material grade validation, and component
cataloging within the engine manufacturing lifecycle.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101904"
UNISPSC_TITLE = "Engine Part"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101904"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Engine Part
    part_id: str
    material_grade: str
    tolerance_verified: bool
    certification_status: str


def inspect_specs(state: State) -> dict[str, Any]:
    """Inspects the input specifications for the engine part."""
    inp = state.get("input") or {}
    p_id = inp.get("part_id", "unknown-engine-part")
    m_grade = inp.get("material", "standard-alloy")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs:{p_id}"],
        "part_id": p_id,
        "material_grade": m_grade
    }


def verify_quality(state: State) -> dict[str, Any]:
    """Verifies if the part meets engine-grade tolerances."""
    m_grade = state.get("material_grade", "standard-alloy")
    # Simulation: High grade materials pass tolerance checks
    passed = "premium" in m_grade or "high" in m_grade or m_grade == "standard-alloy"

    return {
        "log": [f"{UNISPSC_CODE}:verify_quality:tolerance_passed={passed}"],
        "tolerance_verified": passed,
        "certification_status": "ISO-9001-ENG" if passed else "REJECTED"
    }


def catalog_part(state: State) -> dict[str, Any]:
    """Finalizes the component record in the engineering ledger."""
    status = state.get("certification_status", "PENDING")
    p_id = state.get("part_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:catalog_part:finalized"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "part_id": p_id,
            "did": UNISPSC_DID,
            "certified": status == "ISO-9001-ENG",
            "ok": status != "REJECTED",
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_specs", inspect_specs)
_g.add_node("verify_quality", verify_quality)
_g.add_node("catalog_part", catalog_part)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "verify_quality")
_g.add_edge("verify_quality", "catalog_part")
_g.add_edge("catalog_part", END)

graph = _g.compile()
