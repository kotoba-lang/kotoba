# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173808 — Axle Repair (segment 25).

Bespoke graph logic for axle inspection, repair, and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173808"
UNISPSC_TITLE = "Axle Repair"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173808"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Axle Repair
    axle_id: str
    damage_assessment: str
    repair_parts_list: list[str]
    safety_inspection_passed: bool


def inspect_axle(state: State) -> dict[str, Any]:
    inp = state.get("input") or {}
    axle_id = inp.get("axle_id", "GEN-AXLE-001")
    condition = inp.get("condition", "worn_bearings")

    return {
        "log": [f"{UNISPSC_CODE}:inspect_axle: assessed {axle_id} condition as {condition}"],
        "axle_id": axle_id,
        "damage_assessment": condition,
    }


def repair_axle(state: State) -> dict[str, Any]:
    condition = state.get("damage_assessment", "unknown")
    parts = ["grease", "seals"]

    if "bearing" in condition.lower():
        parts.append("roller_bearings")
    if "bent" in condition.lower():
        parts.append("alignment_shims")

    return {
        "log": [f"{UNISPSC_CODE}:repair_axle: applied parts {parts}"],
        "repair_parts_list": parts,
    }


def verify_safety(state: State) -> dict[str, Any]:
    parts = state.get("repair_parts_list", [])
    # Logic: if we have parts applied, we consider the basic repair cycle complete
    passed = len(parts) >= 2

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety: inspection_passed={passed}"],
        "safety_inspection_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "axle_id": state.get("axle_id"),
            "repair_complete": passed,
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_axle", inspect_axle)
_g.add_node("repair_axle", repair_axle)
_g.add_node("verify_safety", verify_safety)

_g.add_edge(START, "inspect_axle")
_g.add_edge("inspect_axle", "repair_axle")
_g.add_edge("repair_axle", "verify_safety")
_g.add_edge("verify_safety", END)

graph = _g.compile()
