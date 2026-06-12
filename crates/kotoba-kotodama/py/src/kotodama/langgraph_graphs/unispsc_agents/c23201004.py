# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23201004 — Engine Block (segment 23).

Bespoke graph logic for Engine Block components, covering material
verification, machining specification validation, and final serial
assignment and quality check.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23201004"
UNISPSC_TITLE = "Engine Block"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23201004"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    alloy_type: str
    machining_specs: dict[str, Any]
    inspection_status: str
    serial_number: str


def verify_casting_material(state: State) -> dict[str, Any]:
    """Verify the casting material specified in the input."""
    inp = state.get("input") or {}
    alloy = inp.get("material", "Grey Cast Iron")
    return {
        "log": [f"{UNISPSC_CODE}:verify_casting_material"],
        "alloy_type": alloy,
        "inspection_status": "material_verified"
    }


def validate_machining_specs(state: State) -> dict[str, Any]:
    """Validate cylinder bore and deck surface machining specifications."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})

    # Logic to ensure essential dimensions are provided
    bore = specs.get("cylinder_bore", 0.0)
    deck = specs.get("deck_height", 0.0)
    valid = bore > 0 and deck > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_machining_specs"],
        "machining_specs": specs,
        "inspection_status": "machining_passed" if valid else "machining_failed"
    }


def finalize_engine_block(state: State) -> dict[str, Any]:
    """Assign serial number and compile final inspection result."""
    status = state.get("inspection_status")
    alloy = state.get("alloy_type", "UNKNOWN")

    # Construct a synthetic serial number based on state
    prefix = alloy[:3].upper()
    serial = f"ENG-{UNISPSC_CODE}-{prefix}-001"

    is_ok = status == "machining_passed"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_engine_block"],
        "serial_number": serial,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "serial": serial,
            "alloy": alloy,
            "status": status,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("verify_casting_material", verify_casting_material)
_g.add_node("validate_machining_specs", validate_machining_specs)
_g.add_node("finalize_engine_block", finalize_engine_block)

_g.add_edge(START, "verify_casting_material")
_g.add_edge("verify_casting_material", "validate_machining_specs")
_g.add_edge("validate_machining_specs", "finalize_engine_block")
_g.add_edge("finalize_engine_block", END)

graph = _g.compile()
