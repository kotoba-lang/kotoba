# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23251501 — Machine Spec (segment 23).

This module provides bespoke logic for processing machine specifications,
ensuring technical parameters meet safety and operational standards.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23251501"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23251501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Machine Spec
    spec_validated: bool
    safety_certification: str
    operational_limits: dict[str, float]
    vendor_id: str


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the incoming machine specification data structure."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    # Simulate validation logic for Machine Spec
    is_valid = "power_rating" in specs and "dimensions" in specs

    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "spec_validated": is_valid,
        "vendor_id": inp.get("vendor_id", "unknown"),
    }


def analyze_safety_envelope(state: State) -> dict[str, Any]:
    """Calculates operational limits and safety ratings based on the spec."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})

    # Domain logic: generate limits based on power rating
    power = specs.get("power_rating", 0)
    limits = {
        "max_rpm": power * 1.5,
        "thermal_threshold": 85.0 if power < 1000 else 110.0
    }

    return {
        "log": [f"{UNISPSC_CODE}:analyze_safety_envelope"],
        "operational_limits": limits,
        "safety_certification": "ISO-9001-PENDING" if power > 0 else "NONE",
    }


def finalize_specification(state: State) -> dict[str, Any]:
    """Compiles the final machine spec record for the ledger."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_specification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "APPROVED" if state.get("spec_validated") else "REJECTED",
            "metadata": {
                "safety_class": state.get("safety_certification"),
                "limits": state.get("operational_limits"),
                "vendor": state.get("vendor_id"),
            },
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_parameters)
_g.add_node("analyze", analyze_safety_envelope)
_g.add_node("finalize", finalize_specification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
