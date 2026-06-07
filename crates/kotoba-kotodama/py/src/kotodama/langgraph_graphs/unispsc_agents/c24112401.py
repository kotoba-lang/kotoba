# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24112401 — Metal containers.

This bespoke graph manages the lifecycle and specification validation for metal
containers within the UNSPSC 24112401 commodity class.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24112401"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24112401"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Metal Containers
    material_grade: str
    capacity_gallons: float
    is_corrosion_resistant: bool
    tare_weight_kg: float
    compliance_standard: str


def validate_material(state: State) -> dict[str, Any]:
    """Validates the material composition of the container."""
    inp = state.get("input") or {}
    material = inp.get("material", "Steel")
    standard = "ISO-15750" if "Steel" in material else "ASTM-B209"

    return {
        "log": [f"{UNISPSC_CODE}:validate_material"],
        "material_grade": material,
        "compliance_standard": standard,
    }


def calculate_metrics(state: State) -> dict[str, Any]:
    """Calculates physical metrics and durability factors."""
    grade = state.get("material_grade", "Steel")
    resistant = any(x in grade for x in ["Stainless", "Galvanized", "Aluminum"])

    return {
        "log": [f"{UNISPSC_CODE}:calculate_metrics"],
        "is_corrosion_resistant": resistant,
        "capacity_gallons": 55.0,  # Default drum size
        "tare_weight_kg": 22.5 if resistant else 18.0,
    }


def register_asset(state: State) -> dict[str, Any]:
    """Finalizes the asset registration in the Etz Hayyim registry."""
    return {
        "log": [f"{UNISPSC_CODE}:register_asset"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material_grade"),
                "standard": state.get("compliance_standard"),
                "metrics": {
                    "capacity": state.get("capacity_gallons"),
                    "tare": state.get("tare_weight_kg"),
                    "durable": state.get("is_corrosion_resistant"),
                }
            },
            "status": "certified"
        },
    }


_g = StateGraph(State)
_g.add_node("validate_material", validate_material)
_g.add_node("calculate_metrics", calculate_metrics)
_g.add_node("register_asset", register_asset)

_g.add_edge(START, "validate_material")
_g.add_edge("validate_material", "calculate_metrics")
_g.add_edge("calculate_metrics", "register_asset")
_g.add_edge("register_asset", END)

graph = _g.compile()
