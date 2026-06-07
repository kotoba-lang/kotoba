# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101512 — Machine Spec.
Bespoke LangGraph implementation for processing industrial machine specifications.
"""

import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101512"
UNISPSC_TITLE = "Machine Spec"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101512"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Machine Spec
    spec_id: str
    parameters: dict[str, Any]
    validation_status: str
    compliance_score: float


def validate_spec(state: State) -> dict[str, Any]:
    """Validates the incoming machine specification schema."""
    inp = state.get("input") or {}
    params = inp.get("parameters", {})

    # Simulate validation logic
    required_keys = {"power_rating", "voltage", "dimensions"}
    provided_keys = set(params.keys())
    missing = required_keys - provided_keys

    status = "VALID" if not missing else f"INVALID: Missing {missing}"

    return {
        "log": [f"{UNISPSC_CODE}:validate_spec -> {status}"],
        "parameters": params,
        "validation_status": status,
        "spec_id": inp.get("id", "unknown-spec")
    }


def analyze_compliance(state: State) -> dict[str, Any]:
    """Analyzes the machine specs against industry standards."""
    params = state.get("parameters") or {}
    score = 1.0

    # Dummy logic: check if voltage is in a standard industrial range
    voltage = params.get("voltage", 0)
    if not (110 <= voltage <= 480):
        score = 0.5

    return {
        "log": [f"{UNISPSC_CODE}:analyze_compliance -> score: {score}"],
        "compliance_score": score
    }


def emit_result(state: State) -> dict[str, Any]:
    """Finalizes the specification report."""
    is_ok = state.get("validation_status") == "VALID" and state.get("compliance_score", 0) > 0.7

    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "spec_id": state.get("spec_id"),
            "is_compliant": is_ok,
            "status": "APPROVED" if is_ok else "REJECTED",
            "metadata": {
                "score": state.get("compliance_score"),
                "segment": UNISPSC_SEGMENT
            }
        }
    }


_g = StateGraph(State)

_g.add_node("validate", validate_spec)
_g.add_node("analyze", analyze_compliance)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
