# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153600 — Welding (segment 23).
Bespoke logic for welding procedure specification (WPS) validation,
operator certification checks, and safety protocol verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153600"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Welding processing
    wps_valid: bool
    operator_certified: bool
    safety_cleared: bool
    process_type: str


def validate_wps(state: State) -> dict[str, Any]:
    """Validates the Welding Procedure Specification (WPS) against project requirements."""
    inp = state.get("input") or {}
    wps_data = inp.get("wps_data", {})
    # Mock validation: requires a standard code and material match
    is_valid = wps_data.get("code") in ["AWS D1.1", "ASME BPVC IX"]
    return {
        "log": [f"{UNISPSC_CODE}:validate_wps"],
        "wps_valid": is_valid,
        "process_type": wps_data.get("process", "unknown"),
    }


def check_operator(state: State) -> dict[str, Any]:
    """Verifies that the welding operator has current certifications for the specified process."""
    inp = state.get("input") or {}
    operator_data = inp.get("operator", {})
    # Mock check: operator must have a valid cert_id
    is_certified = "cert_id" in operator_data and operator_data.get("status") == "active"

    return {
        "log": [f"{UNISPSC_CODE}:check_operator"],
        "operator_certified": is_certified,
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Ensures safety protocols, including PPE and ventilation, are in place."""
    inp = state.get("input") or {}
    safety_data = inp.get("safety", {})
    # Mock verification: requires PPE check and hot work permit
    is_cleared = safety_data.get("ppe_check", False) and safety_data.get("permit", False)

    ok = state.get("wps_valid", False) and state.get("operator_certified", False) and is_cleared

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety"],
        "safety_cleared": is_cleared,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "authorized" if ok else "rejected",
            "wps_valid": state.get("wps_valid"),
            "operator_certified": state.get("operator_certified"),
            "safety_cleared": is_cleared,
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_wps", validate_wps)
_g.add_node("check_operator", check_operator)
_g.add_node("verify_safety", verify_safety)

_g.add_edge(START, "validate_wps")
_g.add_edge("validate_wps", "check_operator")
_g.add_edge("check_operator", "verify_safety")
_g.add_edge("verify_safety", END)

graph = _g.compile()
