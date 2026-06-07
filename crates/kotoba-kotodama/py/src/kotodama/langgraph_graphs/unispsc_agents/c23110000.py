# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23110000 — Machine Part (segment 23).
Bespoke logic for managing machine part metadata, inventory verification, and quality checks.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23110000"
UNISPSC_TITLE = "Machine Part"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23110000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    spec_compliance: bool
    inventory_location: str
    serial_number: str
    maintenance_status: str


def inspect_spec(state: State) -> dict[str, Any]:
    """Validates the technical specifications of the machine part."""
    inp = state.get("input") or {}
    specs = inp.get("specs", {})
    # Logic: verify that material and dimensions are provided in specs
    is_compliant = bool(specs.get("material") and specs.get("dimensions"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_spec"],
        "spec_compliance": is_compliant,
        "serial_number": inp.get("serial_number", "SN-TEMP-2311"),
    }


def verify_availability(state: State) -> dict[str, Any]:
    """Checks the warehouse inventory location for the part."""
    # Route to specific zones based on compliance status
    loc = "WH-SEC-PRIMARY" if state.get("spec_compliance") else "QC-HOLDING-BAY"
    return {
        "log": [f"{UNISPSC_CODE}:verify_availability"],
        "inventory_location": loc,
        "maintenance_status": "READY_FOR_INSTALL" if loc == "WH-SEC-PRIMARY" else "QA_REJECTED",
    }


def register_part(state: State) -> dict[str, Any]:
    """Finalizes the machine part registration in the system."""
    return {
        "log": [f"{UNISPSC_CODE}:register_part"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "serial_number": state.get("serial_number"),
            "status": state.get("maintenance_status"),
            "location": state.get("inventory_location"),
            "verified": state.get("spec_compliance", False),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_spec", inspect_spec)
_g.add_node("verify_availability", verify_availability)
_g.add_node("register_part", register_part)

_g.add_edge(START, "inspect_spec")
_g.add_edge("inspect_spec", "verify_availability")
_g.add_edge("verify_availability", "register_part")
_g.add_edge("register_part", END)

graph = _g.compile()
