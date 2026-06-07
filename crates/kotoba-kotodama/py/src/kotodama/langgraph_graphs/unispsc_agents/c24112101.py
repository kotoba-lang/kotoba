# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112101"
UNISPSC_TITLE = "Cask"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112101"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_grade: str
    capacity_liters: float
    integrity_verified: bool
    batch_serial: str


def validate_cask_spec(state: State) -> dict[str, Any]:
    """Validates the construction specifications for the cask."""
    inp = state.get("input") or {}
    grade = inp.get("material", "Select White Oak")
    capacity = float(inp.get("capacity", 225.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_cask_spec"],
        "material_grade": grade,
        "capacity_liters": capacity,
    }


def pressure_test(state: State) -> dict[str, Any]:
    """Simulates a structural integrity test to ensure the cask is leak-proof."""
    material = state.get("material_grade")
    # Simulation logic: assume integrity for standard materials
    is_valid = material in ["Select White Oak", "American Oak", "French Oak"]
    return {
        "log": [f"{UNISPSC_CODE}:pressure_test"],
        "integrity_verified": is_valid,
    }


def finalize_cask_record(state: State) -> dict[str, Any]:
    """Finalizes the manufacturing record and assigns a serial number."""
    verified = state.get("integrity_verified", False)
    capacity = state.get("capacity_liters", 0.0)
    serial = f"CSK-{UNISPSC_CODE}-{int(capacity)}"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_cask_record"],
        "batch_serial": serial,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "serial_number": serial,
            "volume_l": capacity,
            "certified": verified,
            "status": "READY_FOR_USE" if verified else "REJECTED",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_cask_spec)
_g.add_node("test", pressure_test)
_g.add_node("finalize", finalize_cask_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
