# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26121520 — Wire (segment 26).

Upgraded bespoke logic for Wire. This agent handles specification inspection,
insulation verification, and certification for industrial electrical wire products.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26121520"
UNISPSC_TITLE = "Wire"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26121520"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material: str
    gauge_awg: int
    insulation_type: str
    voltage_max: int
    continuity_verified: bool


def inspect_metallurgy(state: State) -> dict[str, Any]:
    """Inspects the conductor material and wire gauge."""
    inp = state.get("input") or {}
    material = inp.get("material", "Copper")
    gauge = inp.get("gauge_awg", 12)
    return {
        "log": [f"{UNISPSC_CODE}:inspect_metallurgy: {material} AWG {gauge}"],
        "material": material,
        "gauge_awg": gauge,
    }


def verify_insulation(state: State) -> dict[str, Any]:
    """Checks insulation specs and determines maximum safe voltage."""
    inp = state.get("input") or {}
    insulation = inp.get("insulation", "PVC")
    # Simulation: Industrial ratings vs standard
    voltage = 600 if insulation.upper() in ["THHN", "THWN", "XLPE"] else 300
    return {
        "log": [f"{UNISPSC_CODE}:verify_insulation: type={insulation}, max_v={voltage}"],
        "insulation_type": insulation,
        "voltage_max": voltage,
    }


def certifying_test(state: State) -> dict[str, Any]:
    """Simulates a continuity and compliance certification test."""
    is_valid = state.get("gauge_awg", 12) > 0 and state.get("voltage_max", 0) >= 300
    return {
        "log": [f"{UNISPSC_CODE}:certifying_test: pass={is_valid}"],
        "continuity_verified": is_valid,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_valid,
            "summary": f"{state.get('material')} wire, {state.get('insulation_type')} insulation",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_metallurgy", inspect_metallurgy)
_g.add_node("verify_insulation", verify_insulation)
_g.add_node("certifying_test", certifying_test)

_g.add_edge(START, "inspect_metallurgy")
_g.add_edge("inspect_metallurgy", "verify_insulation")
_g.add_edge("verify_insulation", "certifying_test")
_g.add_edge("certifying_test", END)

graph = _g.compile()
