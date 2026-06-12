# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171905 — Valve (segment 25).

Bespoke graph logic for industrial valve components. This agent handles
specification verification, simulated pressure tolerance testing, and
final certification of the valve unit.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171905"
UNISPSC_TITLE = "Valve"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171905"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    valve_type: str
    pressure_rating_psi: int
    material_grade: str
    test_integrity_score: float
    is_compliant: bool


def verify_specs(state: State) -> dict[str, Any]:
    """Analyzes the technical specifications provided in the input."""
    inp = state.get("input") or {}
    v_type = inp.get("valve_type", "ball")
    p_rating = int(inp.get("pressure_rating", 150))
    mat = inp.get("material", "316_stainless_steel")

    return {
        "log": [f"{UNISPSC_CODE}:verify_specs - type={v_type}, psi={p_rating}"],
        "valve_type": v_type,
        "pressure_rating_psi": p_rating,
        "material_grade": mat,
    }


def simulate_pressure_test(state: State) -> dict[str, Any]:
    """Executes a simulated stress test on the valve components."""
    psi = state.get("pressure_rating_psi", 0)
    # Simple logic: valves rated for extremely high or low pressure need extra checks
    score = 0.95 if 100 <= psi <= 5000 else 0.85

    return {
        "log": [f"{UNISPSC_CODE}:simulate_pressure_test - score={score}"],
        "test_integrity_score": score,
        "is_compliant": score > 0.9,
    }


def finalize_certification(state: State) -> dict[str, Any]:
    """Generates the final certification outcome for the valve actor."""
    compliant = state.get("is_compliant", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "certification_status": "APPROVED" if compliant else "DEFERRED",
            "spec_summary": {
                "valve_type": state.get("valve_type"),
                "material": state.get("material_grade"),
                "max_rating": state.get("pressure_rating_psi"),
                "integrity_score": state.get("test_integrity_score")
            },
            "ok": compliant,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specs", verify_specs)
_g.add_node("simulate_pressure_test", simulate_pressure_test)
_g.add_node("finalize_certification", finalize_certification)

_g.add_edge(START, "verify_specs")
_g.add_edge("verify_specs", "simulate_pressure_test")
_g.add_edge("simulate_pressure_test", "finalize_certification")
_g.add_edge("finalize_certification", END)

graph = _g.compile()
