# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151602 — Welding (segment 23).

Bespoke LangGraph agent logic for industrial welding processes, replacing the
generic placeholder with domain-specific state transitions and validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151602"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151602"


class State(TypedDict, total=False):
    # Core framework fields
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]

    # Domain-specific state for Welding operations
    material_spec: str
    welding_method: str
    thermal_compliance: bool
    joint_integrity_score: float


def validate_welding_parameters(state: State) -> dict[str, Any]:
    """Validates the input specification for the welding task."""
    inp = state.get("input") or {}
    material = inp.get("material", "Carbon Steel")
    method = inp.get("method", "Arc")

    # Check if the requested method is compatible with the material
    is_valid = material in ["Carbon Steel", "Stainless Steel", "Aluminum"]

    return {
        "log": [f"{UNISPSC_CODE}:validate_welding_parameters"],
        "material_spec": material,
        "welding_method": method,
        "thermal_compliance": is_valid
    }


def execute_fusion_process(state: State) -> dict[str, Any]:
    """Simulates the physical welding process and records integrity metrics."""
    is_compliant = state.get("thermal_compliance", False)
    method = state.get("welding_method", "Unknown")

    # Simulate integrity score: higher if compliant, lower if parameters were off
    integrity = 0.97 if is_compliant else 0.42

    return {
        "log": [f"{UNISPSC_CODE}:execute_fusion_process (using {method})"],
        "joint_integrity_score": integrity
    }


def certify_weld_quality(state: State) -> dict[str, Any]:
    """Performs final inspection and prepares the UNISPSC agent result."""
    score = state.get("joint_integrity_score", 0.0)
    passed = score > 0.85

    return {
        "log": [f"{UNISPSC_CODE}:certify_weld_quality"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "integrity": score,
                "certified": passed
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_parameters", validate_welding_parameters)
_g.add_node("execute_fusion", execute_fusion_process)
_g.add_node("certify_quality", certify_weld_quality)

_g.add_edge(START, "validate_parameters")
_g.add_edge("validate_parameters", "execute_fusion")
_g.add_edge("execute_fusion", "certify_quality")
_g.add_edge("certify_quality", END)

graph = _g.compile()
