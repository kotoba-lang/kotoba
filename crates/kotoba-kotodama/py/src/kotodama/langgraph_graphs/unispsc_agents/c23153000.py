# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23153000 — Welding (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23153000"
UNISPSC_TITLE = "Welding"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23153000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    welding_method: str
    material_compatibility_verified: bool
    safety_certification_id: str
    thermal_stress_limit: float


def analyze_welding_specs(state: State) -> dict[str, Any]:
    """Analyze input specifications for the welding job."""
    inp = state.get("input") or {}
    method = inp.get("method", "Arc")
    material = inp.get("material", "Steel")

    return {
        "log": [f"{UNISPSC_CODE}:analyze_welding_specs"],
        "welding_method": method,
        "material_compatibility_verified": material in ["Steel", "Aluminum", "Stainless Steel"],
    }


def verify_safety_protocols(state: State) -> dict[str, Any]:
    """Verify that safety protocols are in place for the chosen method."""
    method = state.get("welding_method", "Arc")
    cert_id = f"CERT-{UNISPSC_CODE}-{method.upper()}"

    # Calculate a mock thermal stress limit for the welding operation
    stress_limit = 450.0 if method == "TIG" else 300.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety_protocols"],
        "safety_certification_id": cert_id,
        "thermal_stress_limit": stress_limit,
    }


def execute_welding_certification(state: State) -> dict[str, Any]:
    """Finalize the welding task and emit the certification result."""
    valid = state.get("material_compatibility_verified", False)
    method = state.get("welding_method", "Unknown")

    return {
        "log": [f"{UNISPSC_CODE}:execute_welding_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "method_used": method,
            "certification_id": state.get("safety_certification_id"),
            "status": "APPROVED" if valid else "REJECTED",
            "ok": valid,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze", analyze_welding_specs)
_g.add_node("safety", verify_safety_protocols)
_g.add_node("certify", execute_welding_certification)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "safety")
_g.add_edge("safety", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
