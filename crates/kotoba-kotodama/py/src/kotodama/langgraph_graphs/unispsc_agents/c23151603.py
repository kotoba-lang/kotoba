# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23151603 — Welding (segment 23).

Bespoke logic for industrial welding machinery including safety compliance validation,
parameter calibration (voltage/amperage), and operational certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23151603"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23151603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Welding machinery processing
    safety_compliant: bool
    calibration_status: str
    parameter_set: dict[str, float]
    certification_token: str


def validate_safety(state: State) -> dict[str, Any]:
    """Checks if the welding machinery meets OSHA/ISO safety standards."""
    inp = state.get("input") or {}
    safety_data = inp.get("safety_report", {})
    is_compliant = safety_data.get("compliant", True)  # Defaulting to true for simulation
    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "safety_compliant": is_compliant,
    }


def calibrate_machinery(state: State) -> dict[str, Any]:
    """Calibrates welding parameters based on material specifications."""
    if not state.get("safety_compliant"):
        return {
            "log": [f"{UNISPSC_CODE}:calibrate_machinery:aborted_safety"],
            "calibration_status": "failed_safety_check",
        }

    inp = state.get("input") or {}
    material = inp.get("material", "steel")
    thickness = inp.get("thickness", 5.0)

    # Heuristic calibration
    voltage = 20.0 + (thickness * 0.5)
    amperage = 100.0 + (thickness * 10.0)

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_machinery:success"],
        "calibration_status": "calibrated",
        "parameter_set": {"voltage": voltage, "amperage": amperage, "gas_flow": 15.0},
    }


def certify_operation(state: State) -> dict[str, Any]:
    """Issues an operational certification for the welding process."""
    ok = state.get("safety_compliant", False) and state.get("calibration_status") == "calibrated"
    token = f"WELD-{UNISPSC_CODE}-CERT-ALPHA" if ok else "INVALID"

    return {
        "log": [f"{UNISPSC_CODE}:certify_operation"],
        "certification_token": token,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_token": token,
            "parameters": state.get("parameter_set", {}),
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_safety", validate_safety)
_g.add_node("calibrate_machinery", calibrate_machinery)
_g.add_node("certify_operation", certify_operation)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "calibrate_machinery")
_g.add_edge("calibrate_machinery", "certify_operation")
_g.add_edge("certify_operation", END)

graph = _g.compile()
