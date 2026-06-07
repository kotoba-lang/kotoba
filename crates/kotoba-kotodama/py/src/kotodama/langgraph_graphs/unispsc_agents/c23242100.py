# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23242100 — Machine Attachment (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242100"
UNISPSC_TITLE = "Machine Attachment"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242100"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Machine Attachment domain state
    attachment_serial: str
    target_machine_id: str
    compatibility_certified: bool
    safety_interlock_verified: bool
    installation_torque_nm: float


def validate_compatibility(state: State) -> dict[str, Any]:
    """Ensures the attachment is compatible with the specified machine model."""
    inp = state.get("input") or {}
    serial = inp.get("attachment_serial", "SN-000")
    machine = inp.get("target_machine_id", "M-BASE")

    # Logic: Attachments starting with 'SN' are compatible with machines starting with 'M'
    is_compatible = serial.startswith("SN") and machine.startswith("M")

    return {
        "log": [f"{UNISPSC_CODE}:validate_compatibility"],
        "attachment_serial": serial,
        "target_machine_id": machine,
        "compatibility_certified": is_compatible,
    }


def verify_safety_protocols(state: State) -> dict[str, Any]:
    """Checks safety interlocks and mounting point integrity."""
    certified = state.get("compatibility_certified", False)

    # In a real scenario, this might involve checking sensor data or manual overrides
    interlock_ok = certified

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_protocols"],
        "safety_interlock_verified": interlock_ok,
    }


def finalize_mounting(state: State) -> dict[str, Any]:
    """Finalizes the attachment process and emits the completion result."""
    safe = state.get("safety_interlock_verified", False)
    torque = 45.5 if safe else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_mounting"],
        "installation_torque_nm": torque,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "attachment": state.get("attachment_serial"),
            "machine": state.get("target_machine_id"),
            "torque_applied": torque,
            "status": "installed" if safe else "rejected",
            "ok": safe,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_compatibility", validate_compatibility)
_g.add_node("verify_safety_protocols", verify_safety_protocols)
_g.add_node("finalize_mounting", finalize_mounting)

_g.add_edge(START, "validate_compatibility")
_g.add_edge("validate_compatibility", "verify_safety_protocols")
_g.add_edge("verify_safety_protocols", "finalize_mounting")
_g.add_edge("finalize_mounting", END)

graph = _g.compile()
