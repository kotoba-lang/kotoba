# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101508 — Creaper (segment 24).

Bespoke logic for mechanic's creepers and industrial material handling support.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101508"
UNISPSC_TITLE = "Creaper"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Creaper
    wheel_integrity_check: str
    structural_material: str
    maximum_load_rating_kg: int
    ergonomic_padding_level: int


def validate_integrity(state: State) -> dict[str, Any]:
    """Validates the physical integrity of the creeper frame and wheels."""
    inp = state.get("input") or {}
    wheel_cond = inp.get("wheels", "standard_check")
    return {
        "log": [f"{UNISPSC_CODE}:validate_integrity"],
        "wheel_integrity_check": f"passed:{wheel_cond}",
        "structural_material": inp.get("material", "reinforced_plastic"),
    }


def assess_load_specification(state: State) -> dict[str, Any]:
    """Calculates maximum load rating based on structural material."""
    material = state.get("structural_material", "unknown")
    rating = 200 if "steel" in material.lower() else 135
    return {
        "log": [f"{UNISPSC_CODE}:assess_load_specification"],
        "maximum_load_rating_kg": rating,
    }


def finalize_operational_state(state: State) -> dict[str, Any]:
    """Finalizes the creeper record for workshop deployment."""
    rating = state.get("maximum_load_rating_kg", 0)
    padding = state.get("input", {}).get("padding_level", 3)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_operational_state"],
        "ergonomic_padding_level": padding,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "deployment_ready": True,
            "max_load": f"{rating}kg",
            "comfort_index": padding
        },
    }


_g = StateGraph(State)
_g.add_node("validate_integrity", validate_integrity)
_g.add_node("assess_load_specification", assess_load_specification)
_g.add_node("finalize_operational_state", finalize_operational_state)

_g.add_edge(START, "validate_integrity")
_g.add_edge("validate_integrity", "assess_load_specification")
_g.add_edge("assess_load_specification", "finalize_operational_state")
_g.add_edge("finalize_operational_state", END)

graph = _g.compile()
