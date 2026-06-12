# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101706 — Laser Procurement (segment 22).
Bespoke logic for safety standards validation and export control verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101706"
UNISPSC_TITLE = "Laser Procurement"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101706"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Laser Procurement
    safety_certified: bool
    export_cleared: bool
    authorization_id: str


def validate_safety_standards(state: State) -> dict[str, Any]:
    """Validates the laser safety classification and compliance."""
    inp = state.get("input") or {}
    safety_data = inp.get("safety_data", {})
    # Check for IEC 60825-1 or equivalent certification
    is_certified = safety_data.get("certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety_standards"],
        "safety_certified": is_certified,
    }


def verify_export_controls(state: State) -> dict[str, Any]:
    """Checks for export restrictions and licensing requirements."""
    inp = state.get("input") or {}
    export_data = inp.get("export_data", {})
    # Default to False if restricted and no license provided
    is_restricted = export_data.get("restricted", True)
    has_license = export_data.get("license_valid", False)
    cleared = not is_restricted or has_license

    return {
        "log": [f"{UNISPSC_CODE}:verify_export_controls"],
        "export_cleared": cleared,
    }


def authorize_purchase(state: State) -> dict[str, Any]:
    """Finalizes authorization based on safety and export compliance."""
    ok = state.get("safety_certified", False) and state.get("export_cleared", False)
    auth_id = "LASER-22101706-AUTH" if ok else "DENIED"

    return {
        "log": [f"{UNISPSC_CODE}:authorize_purchase"],
        "authorization_id": auth_id,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "authorization_id": auth_id,
            "status": "authorized" if ok else "denied",
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety_standards", validate_safety_standards)
_g.add_node("verify_export_controls", verify_export_controls)
_g.add_node("authorize_purchase", authorize_purchase)

_g.add_edge(START, "validate_safety_standards")
_g.add_edge("validate_safety_standards", "verify_export_controls")
_g.add_edge("verify_export_controls", "authorize_purchase")
_g.add_edge("authorize_purchase", END)

graph = _g.compile()
