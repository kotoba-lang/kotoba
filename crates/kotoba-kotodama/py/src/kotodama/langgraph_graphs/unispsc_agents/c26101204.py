# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101204 — Motor (segment 26).
Bespoke logic for electrical specification verification, safety compliance, and performance evaluation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101204"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101204"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Motor processing
    specs_verified: bool
    electrical_safety_check: str
    performance_rating: str
    compliance_score: float


def verify_specifications(state: State) -> dict[str, Any]:
    """Validates physical and electrical specifications of the motor."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    required = ["voltage", "power", "rpm"]
    verified = all(k in specs for k in required)

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications"],
        "specs_verified": verified,
    }


def safety_compliance(state: State) -> dict[str, Any]:
    """Ensures the motor meets electrical safety and insulation standards."""
    if not state.get("specs_verified"):
        return {
            "log": [f"{UNISPSC_CODE}:safety_compliance:incomplete_specs"],
            "electrical_safety_check": "FAILED_INCOMPLETE_DATA",
        }

    inp = state.get("input") or {}
    safety = inp.get("safety_data", {})
    insulation_class = safety.get("insulation_class", "F")
    thermal_protection = safety.get("thermal_protection", False)

    passed = thermal_protection and insulation_class in ["F", "H"]

    return {
        "log": [f"{UNISPSC_CODE}:safety_compliance:{'passed' if passed else 'failed'}"],
        "electrical_safety_check": "CERTIFIED" if passed else "NON_COMPLIANT",
        "compliance_score": 1.0 if passed else 0.5,
    }


def evaluate_performance(state: State) -> dict[str, Any]:
    """Analyzes efficiency ratings and performance characteristics."""
    is_safe = state.get("electrical_safety_check") == "CERTIFIED"
    inp = state.get("input") or {}
    performance = inp.get("performance", {})
    efficiency = performance.get("efficiency", 0.0)

    rating = "PREMIUM" if efficiency > 0.9 else "STANDARD" if efficiency > 0.8 else "ECONOMY"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_performance"],
        "performance_rating": rating,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "safety_status": state.get("electrical_safety_check"),
            "rating": rating,
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specifications", verify_specifications)
_g.add_node("safety_compliance", safety_compliance)
_g.add_node("evaluate_performance", evaluate_performance)

_g.add_edge(START, "verify_specifications")
_g.add_edge("verify_specifications", "safety_compliance")
_g.add_edge("safety_compliance", "evaluate_performance")
_g.add_edge("evaluate_performance", END)

graph = _g.compile()
