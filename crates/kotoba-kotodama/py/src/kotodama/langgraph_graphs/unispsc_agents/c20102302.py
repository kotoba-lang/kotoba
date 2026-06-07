# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20102302 — Precision Tool (segment 20).
Bespoke graph logic for precision engineering instrumentation and tooling.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20102302"
UNISPSC_TITLE = "Precision Tool"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20102302"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    calibration_status: str
    tolerance_microns: float
    wear_coefficient: float
    quality_cert_issued: bool


def validate_requirements(state: State) -> dict[str, Any]:
    """Validate tool specifications and tolerance requirements."""
    inp = state.get("input") or {}
    req_tolerance = float(inp.get("tolerance", 0.1))
    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "tolerance_microns": req_tolerance,
    }


def calibrate_instrument(state: State) -> dict[str, Any]:
    """Perform laser-guided calibration and wear analysis."""
    # Simulate high-precision calibration process
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_instrument"],
        "calibration_status": "ISO-9001-CALIBRATED",
        "wear_coefficient": 0.005,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Final quality assurance inspection and certification."""
    is_calibrated = state.get("calibration_status") == "ISO-9001-CALIBRATED"
    is_precise = state.get("tolerance_microns", 1.0) <= 0.5
    certified = is_calibrated and is_precise

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "quality_cert_issued": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": certified,
            "precision_grade": "A" if is_precise else "B",
            "metadata": {
                "calibration": state.get("calibration_status"),
                "wear": state.get("wear_coefficient")
            }
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requirements", validate_requirements)
_g.add_node("calibrate_instrument", calibrate_instrument)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "calibrate_instrument")
_g.add_edge("calibrate_instrument", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
