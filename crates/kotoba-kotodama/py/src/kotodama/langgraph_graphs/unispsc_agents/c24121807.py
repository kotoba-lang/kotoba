# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24121807 — Plastic cans (segment 24).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121807"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121807"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    capacity_ml: int
    polymer_type: str
    is_hazardous_rated: bool
    quality_passed: bool


def validate_can_specs(state: State) -> dict[str, Any]:
    """Inspects the physical specifications of the plastic can."""
    inp = state.get("input") or {}
    capacity = inp.get("capacity_ml", 5000)
    ptype = inp.get("polymer", "HDPE")

    return {
        "log": [f"{UNISPSC_CODE}:validate_can_specs"],
        "capacity_ml": capacity,
        "polymer_type": ptype,
    }


def safety_compliance(state: State) -> dict[str, Any]:
    """Verifies if the can meets hazardous material storage requirements."""
    # Logic: HDPE cans over 1000ml are considered hazardous rated in this simulation
    is_rated = state.get("polymer_type") == "HDPE" and state.get("capacity_ml", 0) >= 1000

    return {
        "log": [f"{UNISPSC_CODE}:safety_compliance"],
        "is_hazardous_rated": is_rated,
        "quality_passed": True,
    }


def finalize_can_record(state: State) -> dict[str, Any]:
    """Finalizes the processing record for the plastic can actor."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_can_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "can_specs": {
                "capacity": state.get("capacity_ml"),
                "polymer": state.get("polymer_type"),
                "hazmat_rated": state.get("is_hazardous_rated"),
            },
            "status": "verified" if state.get("quality_passed") else "failed",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_can_specs)
_g.add_node("compliance", safety_compliance)
_g.add_node("finalize", finalize_can_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compliance")
_g.add_edge("compliance", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
