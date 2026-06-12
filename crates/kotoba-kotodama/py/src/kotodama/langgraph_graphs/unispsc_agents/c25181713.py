# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25181713 — Trailer (segment 25).

Bespoke logic for trailer compliance, payload verification, and roadworthiness
certification. This agent manages the lifecycle of trailer data within the
Unispsc ecosystem, ensuring safety standards for heavy-duty transport units.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25181713"
UNISPSC_TITLE = "Trailer"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25181713"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Trailer-specific domain state
    vin: str
    capacity_kg: int
    axle_count: int
    is_roadworthy: bool
    compliance_flags: list[str]


def inspect_specs(state: State) -> dict[str, Any]:
    """Extracts and validates basic trailer specifications."""
    inp = state.get("input") or {}
    vin = str(inp.get("vin", "")).strip()
    capacity = int(inp.get("capacity_kg", 0))
    axles = int(inp.get("axle_count", 2))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specs"],
        "vin": vin,
        "capacity_kg": capacity,
        "axle_count": axles,
    }


def validate_safety(state: State) -> dict[str, Any]:
    """Checks VIN format and axle-to-capacity safety ratios."""
    vin = state.get("vin", "")
    capacity = state.get("capacity_kg", 0)
    axles = state.get("axle_count", 1)

    flags = []
    if len(vin) != 17:
        flags.append("INVALID_VIN")

    # Safety rule: heavier trailers require more axles for stability
    if capacity > 5000 and axles < 2:
        flags.append("INSUFFICIENT_AXLES")

    is_roadworthy = len(flags) == 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_safety"],
        "is_roadworthy": is_roadworthy,
        "compliance_flags": flags,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Generates the final compliance certificate for the trailer."""
    is_ok = state.get("is_roadworthy", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "details": {
                "vin": state.get("vin"),
                "capacity_kg": state.get("capacity_kg"),
                "axle_count": state.get("axle_count"),
                "compliance_status": "APPROVED" if is_ok else "REJECTED",
                "flags": state.get("compliance_flags", []),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specs", inspect_specs)
_g.add_node("validate_safety", validate_safety)
_g.add_node("emit_certification", emit_certification)

_g.add_edge(START, "inspect_specs")
_g.add_edge("inspect_specs", "validate_safety")
_g.add_edge("validate_safety", "emit_certification")
_g.add_edge("emit_certification", END)

graph = _g.compile()
