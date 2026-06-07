# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151606 —  (segment 23).

Bespoke logic for UNISPSC 23151606, part of Industrial Manufacturing and
Processing Machinery and Accessories. This agent handles machinery
specification validation, safety compliance auditing, and configuration
finalization for industrial equipment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151606"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for industrial machinery
    specs_validated: bool
    safety_audit_passed: bool
    machine_config: dict[str, Any]
    compliance_id: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the industrial machinery specifications against segment standards."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    is_valid = bool(specs and specs.get("power_rating") and specs.get("dimensions"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "specs_validated": is_valid,
        "machine_config": specs,
    }


def safety_audit(state: State) -> dict[str, Any]:
    """Performs a safety compliance audit based on industrial manufacturing codes."""
    if not state.get("specs_validated"):
        return {
            "log": [f"{UNISPSC_CODE}:safety_audit_skipped"],
            "safety_audit_passed": False
        }

    config = state.get("machine_config", {})
    # Mock safety check: ensure emergency stop is present in config
    has_e_stop = config.get("emergency_stop_system", False)

    return {
        "log": [f"{UNISPSC_CODE}:safety_audit_complete"],
        "safety_audit_passed": has_e_stop,
        "compliance_id": f"ISO-23-{UNISPSC_CODE}-REV1" if has_e_stop else ""
    }


def finalize_asset(state: State) -> dict[str, Any]:
    """Finalizes the machinery asset record and emits the result."""
    success = state.get("specs_validated") and state.get("safety_audit_passed")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "compliance_id": state.get("compliance_id"),
            "status": "APPROVED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("audit", safety_audit)
_g.add_node("finalize", finalize_asset)

_g.add_edge(START, "validate")
_g.add_edge("validate", "audit")
_g.add_edge("audit", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
