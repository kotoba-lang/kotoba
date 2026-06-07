# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202401 — Fuel Tank (segment 25).
Bespoke logic for fuel tank procurement and specification validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202401"
UNISPSC_TITLE = "Fuel Tank"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202401"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Fuel Tank
    capacity_liters: float
    material_grade: str
    is_pressurized: bool
    inspection_passed: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Validates physical dimensions and material specs for the fuel tank."""
    inp = state.get("input") or {}
    capacity = float(inp.get("capacity", 0.0))
    material = str(inp.get("material", "Carbon Steel"))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "capacity_liters": capacity,
        "material_grade": material,
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks safety standards and pressurization requirements."""
    inp = state.get("input") or {}
    pressurized = bool(inp.get("pressurized", False))

    # Logic: tanks over 10000L or pressurized tanks over 1000L need manual review
    passed = True
    capacity = state.get("capacity_liters", 0.0)
    if capacity > 10000 or (pressurized and capacity > 1000):
        passed = False

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "is_pressurized": pressurized,
        "inspection_passed": passed,
    }


def finalize_record(state: State) -> dict[str, Any]:
    """Generates the final procurement record for the Fuel Tank."""
    passed = state.get("inspection_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if passed else "REQUIRE_REVIEW",
            "metadata": {
                "capacity": state.get("capacity_liters"),
                "material": state.get("material_grade"),
                "pressurized": state.get("is_pressurized"),
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_specifications)
_g.add_node("verify", verify_compliance)
_g.add_node("finalize", finalize_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
