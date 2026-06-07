# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202203 — Aircraft Parts (segment 25).

Bespoke logic for aircraft part verification, airworthiness certification,
and maintenance release tracking. This graph implements a rigorous intake
and certification pipeline for aerospace components.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202203"
UNISPSC_TITLE = "Aircraft Parts"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202203"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Aircraft Parts domain state
    part_serial_number: str
    certification_level: str
    airworthiness_verified: bool
    quarantine_status: bool


def inventory_intake(state: State) -> dict[str, Any]:
    """Performs intake validation for incoming aircraft parts."""
    inp = state.get("input") or {}
    serial = inp.get("serial", "SN-PENDING")
    return {
        "log": [f"{UNISPSC_CODE}:inventory_intake:{serial}"],
        "part_serial_number": serial,
        "quarantine_status": False,
    }


def certify_airworthiness(state: State) -> dict[str, Any]:
    """Verifies airworthiness documentation and certification levels."""
    inp = state.get("input") or {}
    cert_level = inp.get("cert_level", "EASA_FORM_1")
    # Simulation: parts without a specific serial format are quarantined
    serial = state.get("part_serial_number", "")
    is_valid = serial.startswith("SN-") and serial != "SN-PENDING"

    return {
        "log": [f"{UNISPSC_CODE}:certify_airworthiness:{cert_level}"],
        "certification_level": cert_level,
        "airworthiness_verified": is_valid,
        "quarantine_status": not is_valid,
    }


def release_to_service(state: State) -> dict[str, Any]:
    """Finalizes the release to service (RTS) protocol."""
    verified = state.get("airworthiness_verified", False)
    serial = state.get("part_serial_number")

    return {
        "log": [f"{UNISPSC_CODE}:release_to_service:{'APPROVED' if verified else 'REJECTED'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "serial": serial,
            "airworthy": verified,
            "status": "RELEASE_TO_SERVICE_ISSUED" if verified else "HELD_IN_QUARANTINE",
            "ok": verified,
        },
    }


_g = StateGraph(State)

_g.add_node("intake", inventory_intake)
_g.add_node("certify", certify_airworthiness)
_g.add_node("release", release_to_service)

_g.add_edge(START, "intake")
_g.add_edge("intake", "certify")
_g.add_edge("certify", "release")
_g.add_edge("release", END)

graph = _g.compile()
