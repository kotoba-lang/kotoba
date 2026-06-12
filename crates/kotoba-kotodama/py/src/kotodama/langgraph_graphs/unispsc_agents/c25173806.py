# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173806 — C V Joint (segment 25).

Bespoke graph for Constant Velocity Joint maintenance and certification logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173806"
UNISPSC_TITLE = "C V Joint"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for C V Joint
    joint_type: str
    boot_integrity: str
    grease_quality: float
    vibration_test_passed: bool


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the input specification for the CV Joint component."""
    inp = state.get("input") or {}
    jtype = inp.get("joint_type", "Rzeppa")
    boot = inp.get("boot_condition", "sealed")

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec"],
        "joint_type": jtype,
        "boot_integrity": boot,
    }


def analyze_diagnostics(state: State) -> dict[str, Any]:
    """Analyzes mechanical diagnostics and grease quality."""
    boot = state.get("boot_integrity")
    # Simulation: cracked boot leads to poor grease quality and failed vibration test
    quality = 1.0 if boot == "sealed" else 0.4
    passed = quality > 0.7

    return {
        "log": [f"{UNISPSC_CODE}:analyze_diagnostics"],
        "grease_quality": quality,
        "vibration_test_passed": passed,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final certification result based on diagnostics."""
    passed = state.get("vibration_test_passed", False)
    quality = state.get("grease_quality", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "CERTIFIED" if passed else "REJECTED",
            "metrics": {
                "grease_quality": quality,
                "vibration_test": "PASS" if passed else "FAIL"
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_spec)
_g.add_node("analyze", analyze_diagnostics)
_g.add_node("finalize", finalize_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
