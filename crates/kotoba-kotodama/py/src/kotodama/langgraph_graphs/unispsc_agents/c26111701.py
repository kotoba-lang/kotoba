# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111701 — Battery (segment 26).

Bespoke logic for battery processing, safety inspection, and voltage testing.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111701"
UNISPSC_TITLE = "Battery"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111701"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Battery
    charge_level_percentage: float
    voltage_volts: float
    safety_inspection_passed: bool
    manufacturer_id: str


def inspect_battery(state: State) -> dict[str, Any]:
    """Node: Inspect the battery for manufacturer metadata and safety compliance."""
    inp = state.get("input") or {}
    mfr = inp.get("manufacturer", "UNKNOWN")
    passed = "defect" not in inp.get("notes", "").lower()

    return {
        "log": [f"{UNISPSC_CODE}:inspect_battery"],
        "manufacturer_id": mfr,
        "safety_inspection_passed": passed,
    }


def test_voltage(state: State) -> dict[str, Any]:
    """Node: Simulate a voltage and charge level test."""
    if state.get("safety_inspection_passed"):
        v = 12.6
        c = 98.0
    else:
        v = 0.0
        c = 0.0

    return {
        "log": [f"{UNISPSC_CODE}:test_voltage"],
        "voltage_volts": v,
        "charge_level_percentage": c,
    }


def certify_and_emit(state: State) -> dict[str, Any]:
    """Node: Finalize the state and emit the battery certification result."""
    passed = state.get("safety_inspection_passed", False)
    voltage = state.get("voltage_volts", 0.0)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "certified": passed and voltage > 1.0,
        "metrics": {
            "voltage": voltage,
            "charge": state.get("charge_level_percentage", 0.0),
            "mfr": state.get("manufacturer_id", "N/A"),
        },
    }

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_emit"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_battery)
_g.add_node("test", test_voltage)
_g.add_node("certify", certify_and_emit)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "test")
_g.add_edge("test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
