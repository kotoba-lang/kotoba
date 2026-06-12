# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151821 — Filter cartridge adapter (segment 23).

Bespoke graph logic for industrial filter cartridge adapters, handling
material validation, specification verification, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151821"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151821"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Filter Cartridge Adapters
    adapter_material: str
    micron_rating: float
    seal_integrity_verified: bool
    compatibility_score: float
    certification_label: str


def inspect_adapter(state: State) -> dict[str, Any]:
    """Inspects the physical properties of the filter cartridge adapter."""
    inp = state.get("input") or {}
    material = inp.get("material", "polypropylene")
    micron = float(inp.get("micron", 5.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_adapter"],
        "adapter_material": material,
        "micron_rating": micron,
    }


def validate_filtration_spec(state: State) -> dict[str, Any]:
    """Validates if the adapter meets industrial filtration requirements."""
    material = state.get("adapter_material", "unknown")
    micron = state.get("micron_rating", 0.0)

    # Simple logic: PTFE and Stainless Steel are high-grade
    is_high_grade = material.lower() in ["ptfe", "stainless steel", "316l"]
    verified = micron > 0 and is_high_grade
    score = 0.95 if is_high_grade else 0.75

    return {
        "log": [f"{UNISPSC_CODE}:validate_filtration_spec"],
        "seal_integrity_verified": verified,
        "compatibility_score": score,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Finalizes the process and emits the adapter certification result."""
    score = state.get("compatibility_score", 0.0)
    verified = state.get("seal_integrity_verified", False)

    label = "INDUSTRIAL_GRADE" if score > 0.9 and verified else "STANDARD_GRADE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "certification_label": label,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification": label,
            "verified": verified,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_adapter", inspect_adapter)
_g.add_node("validate_filtration_spec", validate_filtration_spec)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "inspect_adapter")
_g.add_edge("inspect_adapter", "validate_filtration_spec")
_g.add_edge("validate_filtration_spec", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
