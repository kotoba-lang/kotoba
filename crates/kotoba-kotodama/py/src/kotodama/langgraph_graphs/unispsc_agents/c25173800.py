# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173800 — Drivetrain (segment 25).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173800"
UNISPSC_TITLE = "Drivetrain"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173800"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    torque_capacity_nm: float
    gear_ratio: float
    integrity_status: str
    safety_validated: bool


def assess_specifications(state: State) -> dict[str, Any]:
    """Inspects input for drivetrain mechanical specifications."""
    inp = state.get("input") or {}
    # Extract operational parameters from input or defaults
    torque = float(inp.get("torque_nm", 0.0))
    ratio = float(inp.get("gear_ratio", 1.0))

    return {
        "log": [f"{UNISPSC_CODE}:assess_specifications"],
        "torque_capacity_nm": torque,
        "gear_ratio": ratio,
    }


def validate_drivetrain(state: State) -> dict[str, Any]:
    """Performs integrity and safety checks on the drivetrain configuration."""
    torque = state.get("torque_capacity_nm", 0.0)
    # Basic logic: ensure torque doesn't exceed design limits for this segment
    is_safe = 0.0 < torque < 10000.0

    status = "NOMINAL" if is_safe else "EXCEEDS_SPECIFICATION"
    if torque == 0.0:
        status = "INCOMPLETE_DATA"

    return {
        "log": [f"{UNISPSC_CODE}:validate_drivetrain"],
        "integrity_status": status,
        "safety_validated": is_safe,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Compiles the final asset record for the Drivetrain component."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "integrity": state.get("integrity_status"),
            "safety_check": state.get("safety_validated"),
            "telemetry": {
                "configured_torque": state.get("torque_capacity_nm"),
                "gear_ratio": state.get("gear_ratio"),
            },
            "status": "ready" if state.get("safety_validated") else "pending_review",
        },
    }


_g = StateGraph(State)

_g.add_node("assess", assess_specifications)
_g.add_node("validate", validate_drivetrain)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "assess")
_g.add_edge("assess", "validate")
_g.add_edge("validate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
