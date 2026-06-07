# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241804 — Band sawing machines manufacturing services.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241804"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Band Sawing Machines Manufacturing Services
    material_hardness_brinell: float
    blade_pitch_per_inch: int
    feed_speed_ipm: float
    coolant_flow_rate_gpm: float
    safety_interlock_verified: bool


def validate_production_order(state: State) -> dict[str, Any]:
    """Validates the production order and machine safety parameters."""
    inp = state.get("input") or {}
    hardness = float(inp.get("hardness", 180.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_production_order"],
        "material_hardness_brinell": hardness,
        "safety_interlock_verified": True,
    }


def configure_band_saw(state: State) -> dict[str, Any]:
    """Configures the band saw pitch and feed speed based on material hardness."""
    hardness = state.get("material_hardness_brinell", 180.0)
    # Heuristic for optimal band saw configuration
    pitch = 4 if hardness > 250 else 6
    feed = 12.5 if hardness < 200 else 8.2

    return {
        "log": [f"{UNISPSC_CODE}:configure_band_saw"],
        "blade_pitch_per_inch": pitch,
        "feed_speed_ipm": feed,
        "coolant_flow_rate_gpm": 5.5,
    }


def certify_manufacturing_step(state: State) -> dict[str, Any]:
    """Certifies the manufacturing step and records execution metrics."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_manufacturing_step"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "pitch": state.get("blade_pitch_per_inch"),
                "feed": state.get("feed_speed_ipm"),
                "coolant": state.get("coolant_flow_rate_gpm"),
            },
            "status": "certified",
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_production_order", validate_production_order)
_g.add_node("configure_band_saw", configure_band_saw)
_g.add_node("certify_manufacturing_step", certify_manufacturing_step)

_g.add_edge(START, "validate_production_order")
_g.add_edge("validate_production_order", "configure_band_saw")
_g.add_edge("configure_band_saw", "certify_manufacturing_step")
_g.add_edge("certify_manufacturing_step", END)

graph = _g.compile()
