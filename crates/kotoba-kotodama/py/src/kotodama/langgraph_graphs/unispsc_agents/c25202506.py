# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202506 — Aircraft Door (segment 25).

Bespoke graph logic for aircraft door safety inspection, locking mechanism
verification, and airworthiness certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202506"
UNISPSC_TITLE = "Aircraft Door"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202506"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Aircraft Door
    door_type: str
    seal_integrity_verified: bool
    locking_mechanism_status: str
    pressure_test_passed: bool
    maintenance_log_id: str


def inspect_structural_integrity(state: State) -> dict[str, Any]:
    """Inspects the physical structure and seal integrity of the aircraft door."""
    inp = state.get("input") or {}
    door_type = inp.get("door_type", "passenger_main")

    # Simulate a check on seal pressure and gasket wear
    seal_ok = inp.get("seal_condition") != "worn"

    return {
        "log": [f"{UNISPSC_CODE}:inspect_structural_integrity:{door_type}"],
        "door_type": door_type,
        "seal_integrity_verified": seal_ok,
        "maintenance_log_id": inp.get("maint_id", "LOG-000")
    }


def verify_locking_actuators(state: State) -> dict[str, Any]:
    """Checks the engagement of locking bolts and sensor feedback."""
    inp = state.get("input") or {}

    # Simulate verification of dual-redundant locking sensors
    locked = inp.get("lock_state") == "engaged"
    status = "SECURED" if locked else "FAULT_DETECTED"

    return {
        "log": [f"{UNISPSC_CODE}:verify_locking_actuators:{status}"],
        "locking_mechanism_status": status,
        "pressure_test_passed": inp.get("pressure_test", True)
    }


def certify_airworthiness(state: State) -> dict[str, Any]:
    """Issues a final airworthiness result based on inspection and lock status."""
    is_safe = (
        state.get("seal_integrity_verified", False) and
        state.get("locking_mechanism_status") == "SECURED" and
        state.get("pressure_test_passed", False)
    )

    return {
        "log": [f"{UNISPSC_CODE}:certify_airworthiness:{'OK' if is_safe else 'FAIL'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": is_safe,
            "door_type": state.get("door_type"),
            "log_id": state.get("maintenance_log_id")
        }
    }


_g = StateGraph(State)
_g.add_node("inspect_structural_integrity", inspect_structural_integrity)
_g.add_node("verify_locking_actuators", verify_locking_actuators)
_g.add_node("certify_airworthiness", certify_airworthiness)

_g.add_edge(START, "inspect_structural_integrity")
_g.add_edge("inspect_structural_integrity", "verify_locking_actuators")
_g.add_edge("verify_locking_actuators", "certify_airworthiness")
_g.add_edge("certify_airworthiness", END)

graph = _g.compile()
