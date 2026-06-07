# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23242606"
UNISPSC_TITLE = "Skiving"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23242606"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Industrial Skiving
    material_type: str
    target_depth_mm: float
    blade_sharpness_index: float
    feed_rate: int
    uniformity_confirmed: bool


def configure_skiving_machine(state: State) -> dict[str, Any]:
    """Initializes machine settings based on input material properties."""
    inp = state.get("input") or {}
    material = inp.get("material", "leather")
    depth = inp.get("depth", 0.5)

    # Calculate an optimal feed rate based on depth
    calculated_feed = 50 if depth < 1.0 else 30

    return {
        "log": [f"{UNISPSC_CODE}:configure_skiving_machine: {material} at {depth}mm"],
        "material_type": material,
        "target_depth_mm": depth,
        "feed_rate": calculated_feed,
        "blade_sharpness_index": 0.95
    }


def perform_skive_operation(state: State) -> dict[str, Any]:
    """Simulates the physical removal of material layers."""
    sharpness = state.get("blade_sharpness_index", 0.0)
    feed = state.get("feed_rate", 0)

    # Operation is considered uniform if sharpness is high and feed rate is appropriate
    success = sharpness > 0.8 and feed > 0

    return {
        "log": [f"{UNISPSC_CODE}:perform_skive_operation: executed at feed_rate={feed}"],
        "uniformity_confirmed": success,
        "blade_sharpness_index": sharpness - 0.02  # Simulate wear
    }


def verify_and_emit(state: State) -> dict[str, Any]:
    """Quality control check and final data emission."""
    is_uniform = state.get("uniformity_confirmed", False)
    material = state.get("material_type")

    return {
        "log": [f"{UNISPSC_CODE}:verify_and_emit: quality_check={'PASS' if is_uniform else 'FAIL'}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "process_metadata": {
                "material": material,
                "uniformity": is_uniform,
                "remaining_blade_life": state.get("blade_sharpness_index")
            },
            "status": "COMPLETED" if is_uniform else "MANUAL_INSPECTION_REQUIRED"
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_skiving_machine)
_g.add_node("skive", perform_skive_operation)
_g.add_node("verify", verify_and_emit)

_g.add_edge(START, "configure")
_g.add_edge("configure", "skive")
_g.add_edge("skive", "verify")
_g.add_edge("verify", END)

graph = _g.compile()
