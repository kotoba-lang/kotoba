# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201508"
UNISPSC_TITLE = "Aircraft Part"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Aircraft Part
    part_serial_number: str
    faa_certified: bool
    inspection_passed: bool
    airworthiness_status: str


def validate_part_registry(state: State) -> dict[str, Any]:
    """Verifies the part serial number and initial FAA certification markers."""
    inp = state.get("input") or {}
    serial = inp.get("serial_number", "SN-PENDING")
    is_certified = inp.get("faa_certified", False)
    return {
        "log": [f"{UNISPSC_CODE}:validate_part_registry"],
        "part_serial_number": serial,
        "faa_certified": is_certified,
    }


def perform_safety_audit(state: State) -> dict[str, Any]:
    """Simulates a structural integrity and safety audit of the aircraft part."""
    certified = state.get("faa_certified", False)
    serial = state.get("part_serial_number")
    # Audit logic: passes if certified and has a valid serial format
    passed = certified and serial.startswith("SN-") and serial != "SN-PENDING"
    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_audit"],
        "inspection_passed": passed,
    }


def certify_for_service(state: State) -> dict[str, Any]:
    """Assigns final airworthiness status and prepares the output record."""
    passed = state.get("inspection_passed", False)
    status = "SERVICEABLE" if passed else "UNSERVICEABLE"
    return {
        "log": [f"{UNISPSC_CODE}:certify_for_service"],
        "airworthiness_status": status,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial_number": state.get("part_serial_number"),
            "status": status,
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_part_registry)
_g.add_node("audit", perform_safety_audit)
_g.add_node("certify", certify_for_service)

_g.add_edge(START, "validate")
_g.add_edge("validate", "audit")
_g.add_edge("audit", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
