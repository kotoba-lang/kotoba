# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111516 — Power Generation (segment 26).
Bespoke logic for primary battery specification and safety validation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111516"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111516"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    voltage_v: float
    capacity_mah: int
    chemistry: str
    safety_flags: list[str]
    is_validated: bool


def inspect_specs(state: State) -> dict[str, Any]:
    """Node to inspect electrical specifications from input."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 0.0))
    capacity = int(inp.get("capacity", 0))

    log_entry = f"{UNISPSC_CODE}:inspect_specs -> v={voltage}, cap={capacity}"
    return {
        "log": [log_entry],
        "voltage_v": voltage,
        "capacity_mah": capacity,
        "safety_flags": [],
    }


def analyze_chemistry(state: State) -> dict[str, Any]:
    """Node to classify battery chemistry based on voltage profiles."""
    voltage = state.get("voltage_v", 0.0)
    flags = []

    if 3.0 <= voltage <= 4.2:
        chem = "Lithium-ion"
    elif 1.2 <= voltage <= 1.5:
        chem = "Alkaline/NiMH"
    else:
        chem = "Unknown"
        flags.append("Non-standard voltage detected")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_chemistry -> {chem}"],
        "chemistry": chem,
        "safety_flags": flags,
    }


def validate_safety(state: State) -> dict[str, Any]:
    """Final node to verify safety constraints and emit the result."""
    chem = state.get("chemistry", "Unknown")
    flags = state.get("safety_flags", [])

    is_valid = chem != "Unknown" and len(flags) == 0

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "chemistry_type": chem,
        "status": "APPROVED" if is_valid else "REVIEW_REQUIRED",
    }

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety -> valid={is_valid}"],
        "is_validated": is_valid,
        "result": res,
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_specs)
_g.add_node("analyze", analyze_chemistry)
_g.add_node("validate", validate_safety)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "analyze")
_g.add_edge("analyze", "validate")
_g.add_edge("validate", END)

graph = _g.compile()
