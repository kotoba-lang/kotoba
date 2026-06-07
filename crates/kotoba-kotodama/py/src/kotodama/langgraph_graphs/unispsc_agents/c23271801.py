# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23271801"
UNISPSC_TITLE = "Spatter"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23271801"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Anti-spatter compounds (Welding)
    compound_type: str
    application_method: str
    safety_verified: bool
    calculated_volume_liters: float


def inspect_safety(state: State) -> dict[str, Any]:
    """Ensures the anti-spatter compound meets safety and material standards."""
    inp = state.get("input") or {}
    c_type = inp.get("compound_type", "water-based")
    # Simulate a safety check against a known list of approved bases
    approved_bases = ["water-based", "solvent-based", "ceramic", "silicone-free"]
    is_safe = c_type.lower() in approved_bases

    return {
        "log": [f"{UNISPSC_CODE}:inspect_safety"],
        "compound_type": c_type,
        "safety_verified": is_safe,
    }


def plan_application(state: State) -> dict[str, Any]:
    """Calculates required volume based on surface area and validates method."""
    inp = state.get("input") or {}
    method = inp.get("method", "aerosol_spray")
    area = float(inp.get("area_sqm", 1.0))

    # Heuristic: approx 0.15 Liters per square meter for adequate coverage
    volume = round(area * 0.15, 3)

    return {
        "log": [f"{UNISPSC_CODE}:plan_application"],
        "application_method": method,
        "calculated_volume_liters": volume,
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Finalizes the anti-spatter application manifest for welding operations."""
    is_safe = state.get("safety_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "APPROVED" if is_safe else "REJECTED_SAFETY_FAILURE",
            "execution_plan": {
                "material": state.get("compound_type"),
                "method": state.get("application_method"),
                "est_volume_liters": state.get("calculated_volume_liters"),
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect_safety", inspect_safety)
_g.add_node("plan_application", plan_application)
_g.add_node("generate_manifest", generate_manifest)

_g.add_edge(START, "inspect_safety")
_g.add_edge("inspect_safety", "plan_application")
_g.add_edge("plan_application", "generate_manifest")
_g.add_edge("generate_manifest", END)

graph = _g.compile()
