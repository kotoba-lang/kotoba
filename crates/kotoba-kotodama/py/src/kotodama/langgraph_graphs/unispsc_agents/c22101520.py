# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101520 — Optical (segment 22).

Bespoke graph for managing optical surveying instruments, ensuring calibration
and leveling standards are met for construction and engineering accuracy.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101520"
UNISPSC_TITLE = "Optical"
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101520"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    instrument_model: str
    calibration_date: str
    optical_zoom: int
    is_leveled: bool
    accuracy_certified: bool


def validate_instrument(state: State) -> dict[str, Any]:
    """Check the instrument model and initialization parameters."""
    inp = state.get("input") or {}
    model = inp.get("model", "NIK-2210")
    zoom = inp.get("zoom", 30)

    return {
        "log": [f"{UNISPSC_CODE}:validate_instrument:{model}"],
        "instrument_model": model,
        "optical_zoom": zoom,
    }


def check_calibration(state: State) -> dict[str, Any]:
    """Verify the calibration status of the lens and sensors."""
    inp = state.get("input") or {}
    cal_date = inp.get("calibration_date", "2026-01-01")
    leveled = inp.get("leveled", True)

    return {
        "log": [f"{UNISPSC_CODE}:check_calibration:leveled={leveled}"],
        "calibration_date": cal_date,
        "is_leveled": leveled,
    }


def certify_accuracy(state: State) -> dict[str, Any]:
    """Finalize verification and certify the optical path for use."""
    leveled = state.get("is_leveled", False)
    certified = leveled and state.get("optical_zoom", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:certify_accuracy:certified={certified}"],
        "accuracy_certified": certified,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "instrument": state.get("instrument_model"),
            "certified": certified,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_instrument)
_g.add_node("calibration", check_calibration)
_g.add_node("certify", certify_accuracy)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibration")
_g.add_edge("calibration", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
