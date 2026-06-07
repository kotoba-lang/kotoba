# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121320 — Shield (segment 20).

Bespoke graph logic for the Shield actor, managing material analysis,
structural durability assessment, and deployment readiness verification.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121320"
UNISPSC_TITLE = "Shield"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121320"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    shield_material: str
    impact_resistance: float
    thermal_threshold: int
    deployment_status: str


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the shield material and initial resistance parameters."""
    inp = state.get("input") or {}
    material = inp.get("material", "reinforced_alloy")
    # Default resistance for recognized materials
    resistance = 0.92 if material == "reinforced_alloy" else 0.75
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "shield_material": material,
        "impact_resistance": resistance,
    }


def compute_durability(state: State) -> dict[str, Any]:
    """Computes thermal and structural durability based on material specs."""
    resistance = state.get("impact_resistance", 0.0)
    material = state.get("shield_material", "unknown")

    # Determine thermal threshold based on composition
    threshold = 1500 if material == "reinforced_alloy" else 900

    return {
        "log": [f"{UNISPSC_CODE}:compute_durability"],
        "thermal_threshold": threshold,
        "deployment_status": "optimal" if resistance > 0.85 else "stable",
    }


def finalize_status(state: State) -> dict[str, Any]:
    """Packages the final assessment result for the shield deployment."""
    status = state.get("deployment_status", "unknown")
    threshold = state.get("thermal_threshold", 0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "deployment": status,
            "max_temp_celsius": threshold,
            "ok": threshold >= 1000 and status == "optimal",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("durability", compute_durability)
_g.add_node("finalize", finalize_status)

_g.add_edge(START, "validate")
_g.add_edge("validate", "durability")
_g.add_edge("durability", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
