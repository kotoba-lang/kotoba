# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25121704 — Rail.
Bespoke graph logic for rail component specification and safety verification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25121704"
UNISPSC_TITLE = "Rail"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25121704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    rail_grade: str
    gauge_type: str
    weight_per_meter: float
    safety_compliance: bool


def validate_profile(state: State) -> dict[str, Any]:
    """Validates the physical profile and weight specifications of the rail."""
    inp = state.get("input") or {}
    grade = inp.get("grade", "Standard")
    weight = float(inp.get("weight", 60.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_profile"],
        "rail_grade": grade,
        "weight_per_meter": weight,
    }


def verify_metallurgy(state: State) -> dict[str, Any]:
    """Simulates a metallurgical analysis for wear resistance and hardness."""
    grade = state.get("rail_grade", "Standard")
    is_premium = grade.lower() in ["premium", "r350ht", "hardened"]
    return {
        "log": [f"{UNISPSC_CODE}:verify_metallurgy"],
        "safety_compliance": is_premium or state.get("weight_per_meter", 0) > 50,
    }


def certify_rail(state: State) -> dict[str, Any]:
    """Generates the final compliance certification for the rail asset."""
    compliant = state.get("safety_compliance", False)
    return {
        "log": [f"{UNISPSC_CODE}:certify_rail"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "compliant": compliant,
            "metallurgy": state.get("rail_grade"),
            "status": "CERTIFIED" if compliant else "PENDING_REVIEW",
            "did": UNISPSC_DID,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_profile", validate_profile)
_g.add_node("verify_metallurgy", verify_metallurgy)
_g.add_node("certify_rail", certify_rail)

_g.add_edge(START, "validate_profile")
_g.add_edge("validate_profile", "verify_metallurgy")
_g.add_edge("verify_metallurgy", "certify_rail")
_g.add_edge("certify_rail", END)

graph = _g.compile()
