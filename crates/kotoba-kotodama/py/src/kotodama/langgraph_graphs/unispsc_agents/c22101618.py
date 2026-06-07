# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c22101618 —  (segment 22).

Bespoke graph logic for Building and Construction Machinery (Asphalt Pavers).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "22101618"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "22"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c22101618"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for construction machinery
    safety_inspection_passed: bool
    operational_hours: float
    fuel_level_percent: float
    screed_temperature_celsius: float
    paving_speed_m_min: float


def inspect(state: State) -> dict[str, Any]:
    """Perform pre-operational safety and mechanical inspection."""
    inp = state.get("input") or {}
    # Simulate checking fuel and hours from input or defaults
    hours = float(inp.get("hours", 1250.5))
    fuel = float(inp.get("fuel", 85.0))
    passed = fuel > 10.0 and hours < 5000.0

    return {
        "log": [f"{UNISPSC_CODE}:inspect_machinery"],
        "safety_inspection_passed": passed,
        "operational_hours": hours,
        "fuel_level_percent": fuel,
    }


def configure_paving(state: State) -> dict[str, Any]:
    """Set operational parameters for asphalt paving."""
    if not state.get("safety_inspection_passed"):
        return {"log": [f"{UNISPSC_CODE}:configuration_aborted_safety"]}

    # Set standard operating temperatures and speeds
    return {
        "log": [f"{UNISPSC_CODE}:configure_paving_parameters"],
        "screed_temperature_celsius": 150.0,
        "paving_speed_m_min": 5.5,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Emit final status and telemetry summary."""
    ok = state.get("safety_inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "operational_status": "ready" if ok else "maintenance_required",
            "telemetry": {
                "hours": state.get("operational_hours"),
                "temp": state.get("screed_temperature_celsius"),
                "speed": state.get("paving_speed_m_min"),
            },
            "ok": ok,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect)
_g.add_node("configure", configure_paving)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "configure")
_g.add_edge("configure", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
