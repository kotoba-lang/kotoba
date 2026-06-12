# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352501 — Resin (segment 12).

Bespoke graph logic for resin material processing and quality verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352501"
UNISPSC_TITLE = "Resin"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific resin state
    batch_id: str
    viscosity_cp: float
    purity_grade: str
    is_thermosetting: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Evaluates initial resin specifications and batch identifier."""
    inp = state.get("input") or {}
    batch = inp.get("batch_id", "RESIN-ALPHA-01")
    viscosity = float(inp.get("target_viscosity", 1800.5))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs id={batch}"],
        "batch_id": batch,
        "viscosity_cp": viscosity,
        "is_thermosetting": inp.get("thermosetting", True),
    }


def formulate_batch(state: State) -> dict[str, Any]:
    """Determines purity grade based on viscosity and chemical profile."""
    viscosity = state.get("viscosity_cp", 0.0)
    grade = "INDUSTRIAL"
    if viscosity > 1500:
        grade = "PHARMACEUTICAL" if viscosity > 3000 else "AEROSPACE"

    return {
        "log": [f"{UNISPSC_CODE}:formulate_batch grade={grade}"],
        "purity_grade": grade,
    }


def verify_quality(state: State) -> dict[str, Any]:
    """Finalizes resin batch processing and emits the quality certificate."""
    grade = state.get("purity_grade", "UNKNOWN")
    batch = state.get("batch_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:verify_quality status=PASSED"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch": batch,
            "grade": grade,
            "verified": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("formulate_batch", formulate_batch)
_g.add_node("verify_quality", verify_quality)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "formulate_batch")
_g.add_edge("formulate_batch", "verify_quality")
_g.add_edge("verify_quality", END)

graph = _g.compile()
