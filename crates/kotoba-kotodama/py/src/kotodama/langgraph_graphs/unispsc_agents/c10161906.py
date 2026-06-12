# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10161906 — Fertilizer (segment 10).

Bespoke logic for analyzing fertilizer composition, safety verification,
and application guideline generation for agricultural and domestic use.
"""

from __future__ import annotations

import operator
# Use operator.add for log accumulation
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10161906"
UNISPSC_TITLE = "Fertilizer"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10161906"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Fertilizer
    npk_ratio: list[float]
    safety_clearance: bool
    batch_tracking_id: str
    application_rate: str


def validate_composition(state: State) -> dict[str, Any]:
    """Inspects N-P-K levels and assigns a batch tracking ID."""
    inp = state.get("input") or {}
    # N-P-K (Nitrogen, Phosphorus, Potassium)
    npk = inp.get("npk", [0.0, 0.0, 0.0])
    batch_id = inp.get("batch_id", "F-DEFAULT-999")

    # Basic safety: NPK values must be within 0-100 range
    is_safe = len(npk) == 3 and all(0 <= x <= 100 for x in npk)

    return {
        "log": [f"{UNISPSC_CODE}:validate_composition"],
        "npk_ratio": npk,
        "safety_clearance": is_safe,
        "batch_tracking_id": batch_id
    }


def formulate_guidelines(state: State) -> dict[str, Any]:
    """Determines application instructions based on nutrient density."""
    npk = state.get("npk_ratio", [0.0, 0.0, 0.0])
    is_safe = state.get("safety_clearance", False)

    if not is_safe:
        rate = "CRITICAL: Composition safety breach. Disposal required."
    else:
        n, p, k = npk
        if n > 20.0:
            rate = f"High Nitrogen ({n}%): Apply 2.0kg per 100sqm during vegetative phase."
        elif p > 20.0:
            rate = f"High Phosphorus ({p}%): Apply 1.5kg per 100sqm to promote root health."
        else:
            rate = "Balanced Fertilizer: Standard application 2.5kg per 100sqm."

    return {
        "log": [f"{UNISPSC_CODE}:formulate_guidelines"],
        "application_rate": rate
    }


def publish_manifest(state: State) -> dict[str, Any]:
    """Finalizes the fertilizer metadata for the actor response."""
    return {
        "log": [f"{UNISPSC_CODE}:publish_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": state.get("batch_tracking_id"),
            "instructions": state.get("application_rate"),
            "status": "APPROVED" if state.get("safety_clearance") else "REJECTED",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_composition)
_g.add_node("formulate", formulate_guidelines)
_g.add_node("publish", publish_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "formulate")
_g.add_edge("formulate", "publish")
_g.add_edge("publish", END)

graph = _g.compile()
