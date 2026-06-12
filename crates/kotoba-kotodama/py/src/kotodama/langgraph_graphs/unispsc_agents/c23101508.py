# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101508 — Robot (segment 23).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101508"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for "Robot"
    battery_level: float
    system_status: str
    active_command: str
    sensor_array_valid: bool


def boot_sequence(state: State) -> dict[str, Any]:
    """Initializes internal robot systems."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:boot_sequence"],
        "battery_level": float(inp.get("initial_battery", 98.5)),
        "active_command": str(inp.get("command", "STAY")),
        "system_status": "booting",
    }


def health_check(state: State) -> dict[str, Any]:
    """Verifies battery levels and sensor connectivity."""
    battery = state.get("battery_level", 0.0)
    sensors_ok = battery > 10.0

    new_status = "operational" if sensors_ok else "maintenance_required"

    return {
        "log": [f"{UNISPSC_CODE}:health_check"],
        "sensor_array_valid": sensors_ok,
        "system_status": new_status,
    }


def run_actuator(state: State) -> dict[str, Any]:
    """Executes the movement or task command if systems are healthy."""
    cmd = state.get("active_command", "IDLE")
    can_run = state.get("sensor_array_valid", False) and state.get("system_status") == "operational"

    execution_result = "SUCCESS" if can_run else "FAILED_INHIBITED"

    return {
        "log": [f"{UNISPSC_CODE}:run_actuator"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "command_processed": cmd,
            "status": execution_result,
            "ok": can_run,
        },
    }


_g = StateGraph(State)

_g.add_node("boot", boot_sequence)
_g.add_node("check", health_check)
_g.add_node("actuate", run_actuator)

_g.add_edge(START, "boot")
_g.add_edge("boot", "check")
_g.add_edge("check", "actuate")
_g.add_edge("actuate", END)

graph = _g.compile()
