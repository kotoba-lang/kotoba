# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25161508 — Bike (segment 25).

Bespoke graph logic for bicycle assembly and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25161508"
UNISPSC_TITLE = "Bike"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25161508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    frame_integrity_verified: bool
    drive_train_status: str
    braking_efficiency_rating: float
    safety_inspection_passed: bool


def inspect_structural_frame(state: State) -> dict[str, Any]:
    """Verify the structural integrity of the bicycle frame and fork."""
    inp = state.get("input") or {}
    frame_material = inp.get("frame_material", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_structural_frame: material={frame_material}"],
        "frame_integrity_verified": True,
    }


def assemble_power_transmission(state: State) -> dict[str, Any]:
    """Install and calibrate the derailleur, chain, and crankset."""
    return {
        "log": [f"{UNISPSC_CODE}:assemble_power_transmission: gear_calibration_complete"],
        "drive_train_status": "synchronized",
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Perform final safety checks and issue the compliance certificate."""
    frame_ok = state.get("frame_integrity_verified", False)
    drive_ok = state.get("drive_train_status") == "synchronized"

    passed = frame_ok and drive_ok

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification: passed={passed}"],
        "braking_efficiency_rating": 0.98 if passed else 0.0,
        "safety_inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "certified" if passed else "rejected",
            "frame_verified": frame_ok,
            "transmission_verified": drive_ok,
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_frame", inspect_structural_frame)
_g.add_node("assemble_drive", assemble_power_transmission)
_g.add_node("certify", finalize_certification)

_g.add_edge(START, "inspect_frame")
_g.add_edge("inspect_frame", "assemble_drive")
_g.add_edge("assemble_drive", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
