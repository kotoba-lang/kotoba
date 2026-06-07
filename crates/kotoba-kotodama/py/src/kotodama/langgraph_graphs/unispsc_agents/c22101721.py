# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101721 — Laser (segment 22).

This bespoke graph manages safety validation, optical calibration, and
status reporting for industrial laser equipment.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101721"
UNISPSC_TITLE = "Laser"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101721"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields
    wavelength_nm: float
    power_watt: float
    alignment_status: str
    interlock_verified: bool


def validate_safety(state: State) -> dict[str, Any]:
    """Ensures safety interlocks are engaged and parameters are within bounds."""
    inp = state.get("input") or {}
    power = float(inp.get("power", 0.0))
    interlock = bool(inp.get("interlock_engaged", False))
    wavelength = float(inp.get("wavelength", 1064.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "power_watt": power,
        "interlock_verified": interlock,
        "wavelength_nm": wavelength,
    }


def calibrate_optics(state: State) -> dict[str, Any]:
    """Simulates alignment and calibration of the laser beam."""
    if not state.get("interlock_verified"):
        status = "failed_safety_check"
    elif state.get("power_watt", 0) > 5000:
        status = "overpower_protection_active"
    else:
        status = "aligned_and_ready"

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_optics"],
        "alignment_status": status,
    }


def generate_report(state: State) -> dict[str, Any]:
    """Produces the final operational status and telemetry."""
    status = state.get("alignment_status")
    is_ok = status == "aligned_and_ready"

    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "wavelength_nm": state.get("wavelength_nm"),
                "power_watt": state.get("power_watt"),
                "alignment": status,
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_safety", validate_safety)
_g.add_node("calibrate_optics", calibrate_optics)
_g.add_node("generate_report", generate_report)

_g.add_edge(START, "validate_safety")
_g.add_edge("validate_safety", "calibrate_optics")
_g.add_edge("calibrate_optics", "generate_report")
_g.add_edge("generate_report", END)

graph = _g.compile()
