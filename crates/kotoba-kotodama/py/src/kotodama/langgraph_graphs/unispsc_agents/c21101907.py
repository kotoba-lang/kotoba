# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101907"
UNISPSC_TITLE = "Tiller"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101907"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state for Tiller (Agricultural Machinery)
    soil_consistency: str
    target_tillage_depth_mm: int
    blade_integrity_index: float
    safety_interlock_status: bool


def inspect_hardware(state: State) -> dict[str, Any]:
    """Node to verify the tiller's mechanical readiness and safety systems."""
    inp = state.get("input") or {}
    integrity = inp.get("blade_condition", 0.95)
    safety = inp.get("safety_engaged", True)

    return {
        "log": [f"{UNISPSC_CODE}:inspect_hardware"],
        "blade_integrity_index": integrity,
        "safety_interlock_status": safety,
    }


def configure_tillage(state: State) -> dict[str, Any]:
    """Node to determine optimal tillage depth based on soil consistency."""
    inp = state.get("input") or {}
    soil = inp.get("soil_type", "loam")

    # Logic to adjust depth based on soil type
    depth_map = {"clay": 150, "loam": 220, "sandy": 300, "rocky": 100}
    depth = depth_map.get(soil, 180)

    return {
        "log": [f"{UNISPSC_CODE}:configure_tillage"],
        "soil_consistency": soil,
        "target_tillage_depth_mm": depth,
    }


def emit_tillage_report(state: State) -> dict[str, Any]:
    """Node to finalize the operation and package the result data."""
    safety_ok = state.get("safety_interlock_status", False)
    integrity = state.get("blade_integrity_index", 0.0)
    ready = safety_ok and integrity > 0.7

    return {
        "log": [f"{UNISPSC_CODE}:emit_tillage_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "ready_for_dispatch": ready,
            "parameters": {
                "depth_mm": state.get("target_tillage_depth_mm"),
                "soil": state.get("soil_consistency")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_hardware)
_g.add_node("configure", configure_tillage)
_g.add_node("emit", emit_tillage_report)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "configure")
_g.add_edge("configure", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
