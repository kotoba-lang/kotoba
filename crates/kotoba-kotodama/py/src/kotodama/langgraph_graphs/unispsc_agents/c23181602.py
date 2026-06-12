# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181602 — Compressor (segment 23).
Bespoke logic for pressure rating verification, energy efficiency evaluation,
and deployment authorization.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181602"
UNISPSC_TITLE = "Compressor"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181602"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Compressor processing
    pressure_rating_verified: bool
    efficiency_grade: str
    safety_compliance: bool
    deployment_authorized: bool


def inspect_specifications(state: State) -> dict[str, Any]:
    """Analyzes technical specifications including pressure and safety margins."""
    inp = state.get("input") or {}
    specs = inp.get("specifications", {})
    pressure_psi = specs.get("pressure_psi", 0)
    safety_valves = specs.get("safety_valves", False)

    # Logic: Compressors must have safety valves and stay within operational limits
    verified = pressure_psi > 0 and safety_valves

    return {
        "log": [f"{UNISPSC_CODE}:inspect_specifications"],
        "pressure_rating_verified": verified,
        "safety_compliance": safety_valves,
    }


def evaluate_efficiency(state: State) -> dict[str, Any]:
    """Calculates efficiency grade based on energy consumption vs output."""
    inp = state.get("input") or {}
    metrics = inp.get("efficiency_metrics", {})
    ratio = metrics.get("output_energy_ratio", 0.0)

    if ratio >= 0.9:
        grade = "Platinum"
    elif ratio >= 0.75:
        grade = "Gold"
    elif ratio >= 0.6:
        grade = "Silver"
    else:
        grade = "Standard"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_efficiency:{grade}"],
        "efficiency_grade": grade,
    }


def authorize_deployment(state: State) -> dict[str, Any]:
    """Issues final deployment authorization based on technical and efficiency checks."""
    verified = state.get("pressure_rating_verified", False)
    compliant = state.get("safety_compliance", False)
    grade = state.get("efficiency_grade", "Standard")

    # Requirement: Must be verified, compliant, and at least Silver grade
    ok = verified and compliant and grade in ["Platinum", "Gold", "Silver"]

    auth_id = f"DEPLOY-{UNISPSC_CODE}-" + ("PASS" if ok else "FAIL")

    return {
        "log": [f"{UNISPSC_CODE}:authorize_deployment"],
        "deployment_authorized": ok,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "authorization_id": auth_id,
            "efficiency": grade,
            "ok": ok,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_specifications", inspect_specifications)
_g.add_node("evaluate_efficiency", evaluate_efficiency)
_g.add_node("authorize_deployment", authorize_deployment)

_g.add_edge(START, "inspect_specifications")
_g.add_edge("inspect_specifications", "evaluate_efficiency")
_g.add_edge("evaluate_efficiency", "authorize_deployment")
_g.add_edge("authorize_deployment", END)

graph = _g.compile()
