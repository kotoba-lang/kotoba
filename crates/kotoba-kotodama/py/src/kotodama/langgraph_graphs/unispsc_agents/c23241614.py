# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23241614 — Milling (segment 23).

Bespoke LangGraph implementation for industrial milling processes. This agent
simulates machine setup, tool path execution, and quality inspection for
precision material removal.
"""

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241614"
UNISPSC_TITLE = "Milling"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241614"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Milling Domain Fields
    material_stock: str
    tooling_profile: str
    spindle_speed_rpm: int
    feed_rate_mmpm: float
    tolerance_check_passed: bool


def configure_machining(state: State) -> dict[str, Any]:
    """Validates job parameters and sets machine configuration."""
    inp = state.get("input") or {}
    material = inp.get("material", "Aluminum 6061")
    tool = inp.get("tool", "End Mill 10mm")

    # Calculate simulated parameters based on material
    speed = 3000 if "Steel" in material else 6000
    feed = 150.0 if "Steel" in material else 450.0

    return {
        "log": [f"{UNISPSC_CODE}:configure_machining"],
        "material_stock": material,
        "tooling_profile": tool,
        "spindle_speed_rpm": speed,
        "feed_rate_mmpm": feed,
    }


def execute_mill_cycle(state: State) -> dict[str, Any]:
    """Simulates the removal of material through programmed tool paths."""
    material = state.get("material_stock", "Unknown")
    tool = state.get("tooling_profile", "Generic")

    # Simulated logic: successful if parameters are within bounds
    is_valid_run = state.get("spindle_speed_rpm", 0) > 0

    return {
        "log": [f"{UNISPSC_CODE}:execute_mill_cycle_on_{material}_with_{tool}"],
        "tolerance_check_passed": is_valid_run,
    }


def finalize_inspection(state: State) -> dict[str, Any]:
    """Performs final quality assurance and generates the result packet."""
    passed = state.get("tolerance_check_passed", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inspection"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "COMPLETED" if passed else "REJECTED",
            "metrics": {
                "material": state.get("material_stock"),
                "tool": state.get("tooling_profile"),
                "rpm": state.get("spindle_speed_rpm"),
                "feed": state.get("feed_rate_mmpm"),
            },
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("configure", configure_machining)
_g.add_node("execute", execute_mill_cycle)
_g.add_node("inspect", finalize_inspection)

_g.add_edge(START, "configure")
_g.add_edge("configure", "execute")
_g.add_edge("execute", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
