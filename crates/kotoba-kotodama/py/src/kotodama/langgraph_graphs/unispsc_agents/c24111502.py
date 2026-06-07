# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111502 — Paper Bag (segment 24).

Bespoke logic for Paper Bag actor, providing material specification,
load capacity calculation, and production manifest generation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111502"
UNISPSC_TITLE = "Paper Bag"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111502"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_gsm: int
    handle_type: str
    burst_strength_psi: float
    is_fsc_certified: bool


def define_material(state: State) -> dict[str, Any]:
    """Sets the material properties based on input specifications."""
    inp = state.get("input") or {}
    # Default to standard 70 GSM Kraft paper
    gsm = inp.get("gsm", 70)
    handle = inp.get("handle", "flat_paper")

    return {
        "log": [f"{UNISPSC_CODE}:define_material"],
        "material_gsm": gsm,
        "handle_type": handle,
        "is_fsc_certified": inp.get("fsc", True)
    }


def calculate_integrity(state: State) -> dict[str, Any]:
    """Estimates burst strength based on material weight."""
    gsm = state.get("material_gsm", 70)

    # Rough heuristic for paper burst strength
    strength = gsm * 0.45

    return {
        "log": [f"{UNISPSC_CODE}:calculate_integrity"],
        "burst_strength_psi": strength
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Generates the final product manifest for the paper bag."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material_gsm": state.get("material_gsm"),
                "handle_type": state.get("handle_type"),
                "burst_strength_psi": state.get("burst_strength_psi"),
                "fsc_certified": state.get("is_fsc_certified")
            },
            "compliance": "ASTM D6868"
        }
    }


_g = StateGraph(State)
_g.add_node("define_material", define_material)
_g.add_node("calculate_integrity", calculate_integrity)
_g.add_node("generate_manifest", generate_manifest)

_g.add_edge(START, "define_material")
_g.add_edge("define_material", "calculate_integrity")
_g.add_edge("calculate_integrity", "generate_manifest")
_g.add_edge("generate_manifest", END)

graph = _g.compile()
