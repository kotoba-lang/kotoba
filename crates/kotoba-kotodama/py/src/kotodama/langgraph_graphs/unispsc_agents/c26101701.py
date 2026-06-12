# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101701 — Aircraft Part (segment 26).

Bespoke graph logic for aircraft part lifecycle management, including
airworthiness validation, inventory processing, and release certification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101701"
UNISPSC_TITLE = "Aircraft Part"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    part_number: str
    serial_number: str
    maintenance_release_tag: str
    airworthiness_certified: bool


def validate_airworthiness(state: State) -> dict[str, Any]:
    """Validates the part's airworthiness documents and serial history."""
    inp = state.get("input") or {}
    pn = inp.get("part_number", "PN-UNKNOWN")
    sn = inp.get("serial_number", "SN-UNKNOWN")

    # Airworthiness check based on serial complexity for demonstration
    certified = len(sn) >= 8

    return {
        "log": [f"{UNISPSC_CODE}:validate_airworthiness"],
        "part_number": pn,
        "serial_number": sn,
        "airworthiness_certified": certified,
    }


def process_inventory(state: State) -> dict[str, Any]:
    """Updates inventory records and assigns a maintenance release tracking ID."""
    pn = state.get("part_number")
    sn = state.get("serial_number")
    certified = state.get("airworthiness_certified", False)

    # Assign a release tag if certified, otherwise mark for hold
    tag_id = f"MRT-{pn}-{sn[-4:]}" if certified else "MRT-HOLD-INSPECTION"

    return {
        "log": [f"{UNISPSC_CODE}:process_inventory"],
        "maintenance_release_tag": tag_id,
    }


def generate_release_certificate(state: State) -> dict[str, Any]:
    """Finalizes the state and emits the part release certificate."""
    certified = state.get("airworthiness_certified", False)
    tag = state.get("maintenance_release_tag")

    return {
        "log": [f"{UNISPSC_CODE}:generate_release_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "part_metadata": {
                "part_number": state.get("part_number"),
                "serial_number": state.get("serial_number"),
                "release_tag": tag,
                "status": "AIRWORTHY" if certified else "INSPECTION_REQUIRED",
            },
            "ok": certified,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_airworthiness", validate_airworthiness)
_g.add_node("process_inventory", process_inventory)
_g.add_node("generate_release_certificate", generate_release_certificate)

_g.add_edge(START, "validate_airworthiness")
_g.add_edge("validate_airworthiness", "process_inventory")
_g.add_edge("process_inventory", "generate_release_certificate")
_g.add_edge("generate_release_certificate", END)

graph = _g.compile()
