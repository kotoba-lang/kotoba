# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101803 — Moped (segment 25).

Bespoke graph logic for validating moped specifications and determining
regulatory compliance for vehicle registration.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101803"
UNISPSC_TITLE = "Moped"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101803"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Moped
    engine_displacement_cc: int
    top_speed_kph: int
    fuel_type: str
    is_street_legal: bool


def validate_moped_specs(state: State) -> dict[str, Any]:
    """Extract and validate moped specifications from the input payload."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    engine = specs.get("engine_displacement_cc", 0)
    speed = specs.get("top_speed_kph", 0)
    fuel = specs.get("fuel_type", "gasoline")

    return {
        "log": [f"{UNISPSC_CODE}:validate_moped_specs"],
        "engine_displacement_cc": engine,
        "top_speed_kph": speed,
        "fuel_type": fuel,
    }


def assess_regulatory_compliance(state: State) -> dict[str, Any]:
    """Determine if the vehicle meets the legal criteria for a moped classification."""
    # Typical moped classification: <= 50cc and <= 50 kph
    engine = state.get("engine_displacement_cc", 0)
    speed = state.get("top_speed_kph", 0)

    is_legal = engine <= 50 and speed <= 50

    return {
        "log": [f"{UNISPSC_CODE}:assess_regulatory_compliance - legal={is_legal}"],
        "is_street_legal": is_legal,
    }


def finalize_registration(state: State) -> dict[str, Any]:
    """Generate the final registration status and result payload."""
    is_legal = state.get("is_street_legal", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_registration"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_legal else "REJECTED",
            "reason": "Meets classification limits" if is_legal else "Exceeds moped specifications",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_moped_specs)
_g.add_node("assess", assess_regulatory_compliance)
_g.add_node("finalize", finalize_registration)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
