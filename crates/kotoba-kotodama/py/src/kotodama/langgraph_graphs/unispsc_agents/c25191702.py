# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191702 — Alignment (segment 25).

Bespoke logic for vehicle alignment diagnostics and calibration verification.
Part of the Steering and suspension and alignment components category.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191702"
UNISPSC_TITLE = "Alignment"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191702"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for vehicle alignment
    geometric_measurements: dict[str, float]
    target_tolerances: dict[str, float]
    alignment_status: str
    calibration_id: str


def inspect_geometry(state: State) -> dict[str, Any]:
    """Inspects the current geometric alignment parameters of the vehicle."""
    inp = state.get("input") or {}
    # Simulate reading from sensors or input data provided in the request
    measurements = inp.get("measurements", {"camber_l": -1.1, "camber_r": -1.2, "toe_in": 0.15})
    return {
        "log": [f"{UNISPSC_CODE}:inspect_geometry"],
        "geometric_measurements": measurements,
        "calibration_id": inp.get("calibration_id", "CAL-2026-X1"),
    }


def analyze_deviations(state: State) -> dict[str, Any]:
    """Calculates deviations from target alignment specifications."""
    measurements = state.get("geometric_measurements", {})
    targets = {"camber_l": -1.0, "camber_r": -1.0, "toe_in": 0.10}
    tolerances = {"camber": 0.5, "toe": 0.05}

    status = "within_tolerance"
    for key, val in measurements.items():
        target = targets.get(key, 0.0)
        # Extract base component name (e.g., 'camber' from 'camber_l')
        base = key.split('_')[0]
        tol = tolerances.get(base, 0.1)
        if abs(val - target) > tol:
            status = "adjustment_required"
            break

    return {
        "log": [f"{UNISPSC_CODE}:analyze_deviations"],
        "target_tolerances": targets,
        "alignment_status": status,
    }


def finalize_alignment_report(state: State) -> dict[str, Any]:
    """Finalizes the alignment check and generates the result payload."""
    status = state.get("alignment_status", "unknown")
    cal_id = state.get("calibration_id", "N/A")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_alignment_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "alignment_status": status,
            "calibration_id": cal_id,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_geometry)
_g.add_node("analyze", analyze_deviations)
_g.add_node("report", finalize_alignment_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "report")
_g.add_edge("report", END)

graph = _g.compile()
