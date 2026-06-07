# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202602 — Aircraft Parts (segment 25).

Bespoke graph logic for aircraft component verification and airworthiness
assessment within the Etz Hayyim actor network.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202602"
UNISPSC_TITLE = "Aircraft Parts"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Aircraft Parts
    part_number: str
    serial_number: str
    airworthiness_verified: bool
    maintenance_release_found: bool


def identify_component(state: State) -> dict[str, Any]:
    """Extracts component identification data from the input payload."""
    inp = state.get("input") or {}
    pn = inp.get("part_number") or inp.get("pn", "UNKNOWN")
    sn = inp.get("serial_number") or inp.get("sn", "UNKNOWN")
    return {
        "log": [f"{UNISPSC_CODE}:identify_component"],
        "part_number": pn,
        "serial_number": sn,
    }


def verify_airworthiness(state: State) -> dict[str, Any]:
    """Simulates verification of FAA Form 8130-3 or EASA Form 1 documentation."""
    pn = state.get("part_number")
    # Simulation: parts are considered verified if they have a valid identifier
    is_valid = pn != "UNKNOWN"
    return {
        "log": [f"{UNISPSC_CODE}:verify_airworthiness"],
        "airworthiness_verified": is_valid,
        "maintenance_release_found": is_valid,
    }


def emit_inventory_record(state: State) -> dict[str, Any]:
    """Generates the final actor response including compliance status."""
    is_ok = state.get("airworthiness_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "part_metadata": {
                "pn": state.get("part_number"),
                "sn": state.get("serial_number"),
                "certified": is_ok,
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("identify_component", identify_component)
_g.add_node("verify_airworthiness", verify_airworthiness)
_g.add_node("emit_inventory_record", emit_inventory_record)

_g.add_edge(START, "identify_component")
_g.add_edge("identify_component", "verify_airworthiness")
_g.add_edge("verify_airworthiness", "emit_inventory_record")
_g.add_edge("emit_inventory_record", END)

graph = _g.compile()
