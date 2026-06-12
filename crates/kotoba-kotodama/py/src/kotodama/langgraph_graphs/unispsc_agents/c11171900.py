# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11171900 — Processor (segment 11).

Bespoke LangGraph implementation for processing inedible animal products.
This agent handles the validation, transformation, and quality reporting
for animal-derived materials in the industrial supply chain.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11171900"
UNISPSC_TITLE = "Processor"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11171900"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for an Animal Product Processor
    material_type: str
    processing_temp_celsius: float
    batch_yield_percentage: float
    sterilization_confirmed: bool


def prepare_material(state: State) -> dict[str, Any]:
    """Analyzes input material and prepares the processing environment."""
    inp = state.get("input") or {}
    material = inp.get("material", "inedible_animal_byproduct")
    target_temp = float(inp.get("target_temp", 85.0))

    return {
        "log": [f"{UNISPSC_CODE}:prepare_material -> {material}"],
        "material_type": material,
        "processing_temp_celsius": target_temp,
        "sterilization_confirmed": False,
    }


def execute_transformation(state: State) -> dict[str, Any]:
    """Performs the industrial processing of the animal product."""
    temp = state.get("processing_temp_celsius", 0.0)
    # Simulate sterilization requirement (e.g., must be > 70C)
    is_sterile = temp >= 72.0

    return {
        "log": [f"{UNISPSC_CODE}:execute_transformation (sterile={is_sterile})"],
        "sterilization_confirmed": is_sterile,
        "batch_yield_percentage": 94.5 if is_sterile else 0.0,
    }


def generate_shipment_manifest(state: State) -> dict[str, Any]:
    """Finalizes the process and emits the manifest and quality certificate."""
    is_sterile = state.get("sterilization_confirmed", False)
    yield_val = state.get("batch_yield_percentage", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:generate_shipment_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "quality_report": {
                "material": state.get("material_type"),
                "sterilization": "pass" if is_sterile else "fail",
                "yield": yield_val,
            },
            "ok": is_sterile and yield_val > 0,
        },
    }


_g = StateGraph(State)

_g.add_node("prepare_material", prepare_material)
_g.add_node("execute_transformation", execute_transformation)
_g.add_node("generate_shipment_manifest", generate_shipment_manifest)

_g.add_edge(START, "prepare_material")
_g.add_edge("prepare_material", "execute_transformation")
_g.add_edge("execute_transformation", "generate_shipment_manifest")
_g.add_edge("generate_shipment_manifest", END)

graph = _g.compile()
