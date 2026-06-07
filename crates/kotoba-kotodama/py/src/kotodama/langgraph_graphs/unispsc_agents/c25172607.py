# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25172607 — Vehicle Part (segment 25).

Bespoke logic for vehicle part inventory, VIN compatibility verification,
and warehouse slot allocation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172607"
UNISPSC_TITLE = "Vehicle Part"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172607"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Vehicle Part
    part_id: str
    vin_compatibility: bool
    warehouse_slot: str
    inspection_passed: bool


def validate_part(state: State) -> dict[str, Any]:
    """Validates the part ID and performs a simulated quality inspection."""
    inp = state.get("input") or {}
    part_id = inp.get("part_id", "PART-000")
    # Simulation: parts with ID length > 5 pass inspection
    valid = len(part_id) > 5
    return {
        "log": [f"{UNISPSC_CODE}:validate_part:{part_id}"],
        "part_id": part_id,
        "inspection_passed": valid,
    }


def check_compatibility(state: State) -> dict[str, Any]:
    """Checks the part against a specific Vehicle Identification Number (VIN)."""
    inp = state.get("input") or {}
    vin = inp.get("vin", "GENERIC-VIN")
    # Simulation: assume compatibility if VIN is provided and inspection passed
    compatible = "vin" in inp and state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:check_compatibility:{vin}:{compatible}"],
        "vin_compatibility": compatible,
    }


def locate_inventory(state: State) -> dict[str, Any]:
    """Assigns a warehouse location slot for the vehicle part."""
    part_id = state.get("part_id", "UNK")
    slot = f"SEC-25-R4-{part_id[-3:]}" if state.get("inspection_passed") else "QUARANTINE-BIN"
    return {
        "log": [f"{UNISPSC_CODE}:locate_inventory:{slot}"],
        "warehouse_slot": slot,
    }


def emit_result(state: State) -> dict[str, Any]:
    """Prepares the final result payload with metadata and status."""
    success = state.get("vin_compatibility", False) and state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "part_id": state.get("part_id"),
            "slot": state.get("warehouse_slot"),
            "status": "APPROVED" if success else "REJECTED",
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_part)
_g.add_node("compatibility", check_compatibility)
_g.add_node("inventory", locate_inventory)
_g.add_node("emit", emit_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compatibility")
_g.add_edge("compatibility", "inventory")
_g.add_edge("inventory", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
