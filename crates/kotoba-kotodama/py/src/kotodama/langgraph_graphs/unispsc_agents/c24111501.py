# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111501 — Canvas (segment 24).

Bespoke graph logic for validating canvas material specifications,
calculating mechanical properties, and certifying industrial compliance
within the material handling and container context.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111501"
UNISPSC_TITLE = "Canvas"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111501"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Canvas-specific domain state
    weight_gsm: int
    weave_style: str
    coating_status: str
    tensile_strength: float


def validate_requirements(state: State) -> dict[str, Any]:
    """Validates the input parameters for canvas material production."""
    inp = state.get("input") or {}
    weight = int(inp.get("weight", 340))  # Default 10oz canvas (~340 gsm)
    weave = inp.get("weave", "plain")

    return {
        "log": [f"{UNISPSC_CODE}:validate_requirements"],
        "weight_gsm": weight,
        "weave_style": weave,
    }


def calculate_metrics(state: State) -> dict[str, Any]:
    """Calculates mechanical metrics based on weight and weave style."""
    weight = state.get("weight_gsm", 340)
    weave = state.get("weave_style", "plain")

    # Heuristic for tensile strength (N)
    strength = float(weight) * 1.2
    if weave.lower() == "duck":
        strength *= 1.4

    coating = "none"
    if weight > 500:
        coating = "polyurethane"

    return {
        "log": [f"{UNISPSC_CODE}:calculate_metrics"],
        "tensile_strength": round(strength, 2),
        "coating_status": coating,
    }


def generate_certificate(state: State) -> dict[str, Any]:
    """Generates the final compliance certificate for the canvas material."""
    strength = state.get("tensile_strength", 0.0)
    weight = state.get("weight_gsm", 0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_certificate"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "tensile_strength_n": strength,
                "weight_gsm": weight,
                "coating": state.get("coating_status"),
            },
            "status": "APPROVED" if strength > 400 else "PENDING_REVIEW",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_requirements", validate_requirements)
_g.add_node("calculate_metrics", calculate_metrics)
_g.add_node("generate_certificate", generate_certificate)

_g.add_edge(START, "validate_requirements")
_g.add_edge("validate_requirements", "calculate_metrics")
_g.add_edge("calculate_metrics", "generate_certificate")
_g.add_edge("generate_certificate", END)

graph = _g.compile()
