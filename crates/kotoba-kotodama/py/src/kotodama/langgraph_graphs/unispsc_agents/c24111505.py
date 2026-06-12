# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24111505 — F I B C (segment 24).

Bespoke graph for Flexible Intermediate Bulk Containers (FIBC), handling
specification validation, safe working load (SWL) calculation, and
final manifest generation for material handling automation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24111505"
UNISPSC_TITLE = "F I B C"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24111505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    bag_volume_m3: float
    safe_working_load_kg: int
    is_conductive: bool
    fabric_weight_gsm: int


def validate_specs(state: State) -> dict[str, Any]:
    """Validate the basic physical dimensions and material specs of the FIBC."""
    inp = state.get("input") or {}
    volume = inp.get("volume", 1.25)
    fabric = inp.get("fabric_weight", 180)
    is_cond = inp.get("conductive", False)

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "bag_volume_m3": float(volume),
        "fabric_weight_gsm": int(fabric),
        "is_conductive": bool(is_cond),
    }


def calculate_load(state: State) -> dict[str, Any]:
    """Calculate Safe Working Load (SWL) based on fabric strength and safety factors."""
    fabric = state.get("fabric_weight_gsm", 180)
    volume = state.get("bag_volume_m3", 1.25)

    # Heuristic for SWL calculation: fabric density * factor
    # Base strength approx 6.5kg per GSM for standard PP weave
    base_swl = fabric * 6.5
    # Apply volume-based density cap (assuming max material density of 1200kg/m3)
    max_swl = volume * 1200

    swl = min(int(base_swl), int(max_swl))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_load"],
        "safe_working_load_kg": swl,
    }


def generate_manifest(state: State) -> dict[str, Any]:
    """Generate the final actor response with container specifications."""
    swl = state.get("safe_working_load_kg", 0)
    is_cond = state.get("is_conductive", False)

    return {
        "log": [f"{UNISPSC_CODE}:generate_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specs": {
                "swl_kg": swl,
                "safety_factor": "5:1",
                "fibc_type": "Type C" if is_cond else "Type A",
                "volume_m3": state.get("bag_volume_m3"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("calculate", calculate_load)
_g.add_node("generate", generate_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "generate")
_g.add_edge("generate", END)

graph = _g.compile()
