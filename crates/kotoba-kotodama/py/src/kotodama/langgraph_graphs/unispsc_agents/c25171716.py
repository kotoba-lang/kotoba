# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25171716 — Brake Line (segment 25).

Bespoke agent logic for managing brake line specifications, material
verification, and pressure rating compliance.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25171716"
UNISPSC_TITLE = "Brake Line"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25171716"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Brake Line component management
    material_grade: str
    pressure_rating_psi: int
    length_mm: float
    safety_certified: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input specifications for the brake line component."""
    inp = state.get("input") or {}
    length = float(inp.get("length_mm", 0.0))
    material = str(inp.get("material", "standard_steel"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "length_mm": length,
        "material_grade": material,
    }


def verify_pressure_rating(state: State) -> dict[str, Any]:
    """Simulates pressure rating verification based on material grade."""
    material = state.get("material_grade", "unknown")

    # Simulated material safety thresholds
    ratings = {
        "standard_steel": 2500,
        "stainless_steel": 4500,
        "copper_nickel": 3200,
    }
    rating = ratings.get(material, 1800)

    return {
        "log": [f"{UNISPSC_CODE}:verify_pressure_rating"],
        "pressure_rating_psi": rating,
        "safety_certified": rating >= 2000,
    }


def emit_certification(state: State) -> dict[str, Any]:
    """Generates the final compliance manifest for the brake line."""
    status = "APPROVED" if state.get("safety_certified") else "REJECTED"

    return {
        "log": [f"{UNISPSC_CODE}:emit_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "material": state.get("material_grade"),
                "length": state.get("length_mm"),
                "max_pressure_psi": state.get("pressure_rating_psi"),
            },
            "compliance_status": status,
            "ok": state.get("safety_certified", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("verify_pressure_rating", verify_pressure_rating)
_g.add_node("emit_certification", emit_certification)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "verify_pressure_rating")
_g.add_edge("verify_pressure_rating", "emit_certification")
_g.add_edge("emit_certification", END)

graph = _g.compile()
