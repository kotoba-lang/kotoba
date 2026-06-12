# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102402 — Insect traps (segment 21).

Bespoke graph logic for monitoring and managing insect trap deployments.
This agent handles trap validation, catch processing, and reporting.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102402"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102402"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Insect Traps
    trap_type: str
    lure_active: bool
    pest_count: int
    battery_level: float


def validate_deployment(state: State) -> dict[str, Any]:
    """Validates the trap deployment configuration and battery status."""
    inp = state.get("input") or {}
    trap_type = inp.get("type", "pheromone")
    lure_active = inp.get("lure_enabled", True)
    battery = float(inp.get("battery_voltage", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_deployment"],
        "trap_type": trap_type,
        "lure_active": lure_active,
        "battery_level": battery,
    }


def process_catch(state: State) -> dict[str, Any]:
    """Processes sensor data to update the pest count catch."""
    inp = state.get("input") or {}
    captured = int(inp.get("count", 0))

    return {
        "log": [f"{UNISPSC_CODE}:process_catch"],
        "pest_count": captured,
    }


def emit_report(state: State) -> dict[str, Any]:
    """Finalizes the monitoring session and emits the telemetry report."""
    status = "low_power" if state.get("battery_level", 0) < 20 else "operational"

    return {
        "log": [f"{UNISPSC_CODE}:emit_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "trap_type": state.get("trap_type"),
                "lure_active": state.get("lure_active"),
                "pests_captured": state.get("pest_count"),
                "system_status": status,
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_deployment", validate_deployment)
_g.add_node("process_catch", process_catch)
_g.add_node("emit_report", emit_report)

_g.add_edge(START, "validate_deployment")
_g.add_edge("validate_deployment", "process_catch")
_g.add_edge("process_catch", "emit_report")
_g.add_edge("emit_report", END)

graph = _g.compile()
