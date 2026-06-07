# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151506 — Zirconium (segment 10).

Bespoke logic for zirconium material assessment, specializing in purity
verification and nuclear-grade compliance checks for industrial use cases.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151506"
UNISPSC_TITLE = "Zirconium"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    purity_level: float
    hafnium_ppm: float
    is_nuclear_compliant: bool
    batch_id: str


def assay_material(state: State) -> dict[str, Any]:
    """Analyzes the input for zirconium purity and impurity levels."""
    inp = state.get("input") or {}
    purity = float(inp.get("purity_level", 0.0))
    hafnium = float(inp.get("hafnium_ppm", 1000.0))
    batch = inp.get("batch_id", "ZR-UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:assay_material (batch {batch})"],
        "purity_level": purity,
        "hafnium_ppm": hafnium,
        "batch_id": batch,
    }


def verify_nuclear_grade(state: State) -> dict[str, Any]:
    """Checks if the zirconium meets the low-hafnium requirement for nuclear reactors."""
    # Nuclear grade zirconium typically requires hafnium levels < 100 ppm
    is_compliant = state.get("hafnium_ppm", 1000.0) < 100.0

    status = "REJECTED" if not is_compliant else "CERTIFIED"
    return {
        "log": [f"{UNISPSC_CODE}:verify_nuclear_grade - {status}"],
        "is_nuclear_compliant": is_compliant,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Constructs the final result based on compliance and purity data."""
    is_ok = state.get("purity_level", 0.0) > 99.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "batch": state.get("batch_id"),
            "nuclear_grade": state.get("is_nuclear_compliant"),
            "certified": is_ok,
            "did": UNISPSC_DID,
            "status": "PASS" if is_ok else "FAIL",
        },
    }


_g = StateGraph(State)
_g.add_node("assay", assay_material)
_g.add_node("verify", verify_nuclear_grade)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "assay")
_g.add_edge("assay", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
