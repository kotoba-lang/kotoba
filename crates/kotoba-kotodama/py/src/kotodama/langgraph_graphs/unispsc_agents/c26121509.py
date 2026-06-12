# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26121509 — Wire (segment 26).

Bespoke graph for electrical and industrial wire specification, conductivity
testing, and shipment preparation. This agent manages state transitions for
wire gauges, materials, and insulation ratings.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26121509"
UNISPSC_TITLE = "Wire"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26121509"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Wire
    gauge_awg: float
    material: str
    insulation_rating: str
    continuity_verified: bool


def specify_characteristics(state: State) -> dict[str, Any]:
    """Parses input requirements for wire physical properties."""
    inp = state.get("input") or {}
    gauge = float(inp.get("gauge", 14.0))
    material = str(inp.get("material", "Copper"))
    insulation = str(inp.get("insulation", "THHN"))

    return {
        "log": [f"{UNISPSC_CODE}:specify_characteristics(gauge={gauge}, material={material})"],
        "gauge_awg": gauge,
        "material": material,
        "insulation_rating": insulation,
        "continuity_verified": False,
    }


def perform_quality_test(state: State) -> dict[str, Any]:
    """Simulates electrical continuity and material integrity checks."""
    material = state.get("material", "").lower()
    # Basic logic: conductive metals pass the test
    is_conductive = material in ["copper", "aluminum", "silver", "gold"]

    return {
        "log": [f"{UNISPSC_CODE}:perform_quality_test(conductive={is_conductive})"],
        "continuity_verified": is_conductive,
    }


def finalize_inventory_record(state: State) -> dict[str, Any]:
    """Prepares the final result with full specification and test status."""
    passed = state.get("continuity_verified", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "gauge_awg": state.get("gauge_awg"),
                "material": state.get("material"),
                "insulation": state.get("insulation_rating"),
            },
            "quality_control": {
                "continuity_test": "PASSED" if passed else "FAILED",
                "disposition": "REEL_READY" if passed else "HOLD_FOR_SCRAP",
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)
_g.add_node("specify", specify_characteristics)
_g.add_node("test", perform_quality_test)
_g.add_node("finalize", finalize_inventory_record)

_g.add_edge(START, "specify")
_g.add_edge("specify", "test")
_g.add_edge("test", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
