# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24102109 — Sack Holder (segment 24).

Bespoke logic for managing sack holder specifications, structural integrity
checks, and safety margin verification for industrial material handling.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24102109"
UNISPSC_TITLE = "Sack Holder"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24102109"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Sack Holder
    material_grade: str
    volume_capacity_liters: float
    integrity_verified: bool
    safety_margin_factor: float


def inspect_requirements(state: State) -> dict[str, Any]:
    """Validate incoming engineering requirements for the sack holder unit."""
    inp = state.get("input") or {}
    grade = str(inp.get("grade", "standard-duty"))
    volume = float(inp.get("volume", 50.0))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_requirements"],
        "material_grade": grade,
        "volume_capacity_liters": volume,
    }


def verify_structural_integrity(state: State) -> dict[str, Any]:
    """Analyze if the material grade matches the intended volume capacity."""
    grade = state.get("material_grade")
    volume = state.get("volume_capacity_liters", 0.0)

    # Logic: Industrial/High-capacity units require premium or heavy-duty grades
    is_valid = True
    if volume > 100.0 and grade == "standard-duty":
        is_valid = False

    return {
        "log": [f"{UNISPSC_CODE}:verify_structural_integrity"],
        "integrity_verified": is_valid,
    }


def assess_safety_margins(state: State) -> dict[str, Any]:
    """Calculate a safety margin factor based on integrity verification."""
    verified = state.get("integrity_verified", False)
    grade = state.get("material_grade")

    # Base safety factor adjusted by material quality
    factor = 1.2 if verified else 0.75
    if grade == "heavy-duty":
        factor += 0.3

    return {
        "log": [f"{UNISPSC_CODE}:assess_safety_margins"],
        "safety_margin_factor": round(factor, 2),
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Compile final results and certification status into the agent result."""
    safety_factor = state.get("safety_margin_factor", 0.0)
    is_certified = safety_factor >= 1.0

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certified": is_certified,
            "analysis": {
                "material": state.get("material_grade"),
                "capacity": state.get("volume_capacity_liters"),
                "safety_factor": safety_factor,
            },
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_requirements)
_g.add_node("verify", verify_structural_integrity)
_g.add_node("assess", assess_safety_margins)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "verify")
_g.add_edge("verify", "assess")
_g.add_edge("assess", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
