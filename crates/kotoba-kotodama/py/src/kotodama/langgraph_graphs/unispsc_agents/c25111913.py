# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111913 — Deck Hatch (segment 25).

Bespoke graph logic for marine/industrial deck hatch components.
This agent validates mechanical specifications, integrity checks, and safety latching.
"""

from __future__ import annotations

import operator
# Note: operator.add is used for list concatenation in State log field
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111913"
UNISPSC_TITLE = "Deck Hatch"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111913"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Deck Hatch
    material_spec: str
    dimensions_verified: bool
    seal_integrity_score: float
    latch_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the material and dimensional specifications of the deck hatch."""
    inp = state.get("input") or {}
    material = inp.get("material", "marine-grade-aluminum")
    dims = inp.get("dimensions", {})

    # Simulate validation logic: dimensions must be present
    verified = bool(dims.get("length") and dims.get("width"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "material_spec": material,
        "dimensions_verified": verified,
    }


def inspect_integrity(state: State) -> dict[str, Any]:
    """Performs integrity check on seals and latching mechanisms."""
    # Integrity depends on dimensions being verified in previous step
    if state.get("dimensions_verified"):
        score = 0.98
        status = "engaged"
    else:
        score = 0.45
        status = "mechanical_failure"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_integrity"],
        "seal_integrity_score": score,
        "latch_status": status,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Emits the final inspection and configuration record."""
    # Pass if integrity score meets threshold
    ok = state.get("seal_integrity_score", 0) > 0.9

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material": state.get("material_spec"),
            "latch_status": state.get("latch_status"),
            "integrity_passed": ok,
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("inspect_integrity", inspect_integrity)
_g.add_node("finalize_record", finalize_record)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "inspect_integrity")
_g.add_edge("inspect_integrity", "finalize_record")
_g.add_edge("finalize_record", END)

graph = _g.compile()
