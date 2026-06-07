# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10171603"
UNISPSC_TITLE = "Mining Tool"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10171603"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke domain fields for Mining Tool
    tool_status: str
    extracted_weight: float
    drill_rpm: int
    overheat_detected: bool


def check_tool_telemetry(state: State) -> dict[str, Any]:
    """Evaluates the mining tool telemetry and operational status."""
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 1200)
    temp = inp.get("temperature", 45.0)

    overheat = temp > 95.0
    status = "OPERATIONAL" if not overheat else "ERROR_OVERHEAT"

    return {
        "log": [f"{UNISPSC_CODE}:check_tool_telemetry - status: {status}"],
        "tool_status": status,
        "drill_rpm": rpm,
        "overheat_detected": overheat
    }


def execute_mining_cycle(state: State) -> dict[str, Any]:
    """Simulates a tool-based mining cycle and tracks extracted material."""
    if state.get("overheat_detected"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_mining_cycle - Execution skipped: safety override"],
            "extracted_weight": 0.0
        }

    # Calculate extraction based on RPM
    rpm = state.get("drill_rpm", 0)
    weight = (rpm / 100.0) * 12.5

    return {
        "log": [f"{UNISPSC_CODE}:execute_mining_cycle - Extracted {weight:.2f} units"],
        "extracted_weight": weight
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Produces the final summary and state for the mining operation."""
    weight = state.get("extracted_weight", 0.0)
    status = state.get("tool_status", "UNKNOWN")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry - Completed with status {status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "total_weight": weight,
                "tool_health": "GREEN" if status == "OPERATIONAL" else "RED",
                "cycle_ok": weight > 0
            }
        }
    }


_g = StateGraph(State)
_g.add_node("check_telemetry", check_tool_telemetry)
_g.add_node("mining_cycle", execute_mining_cycle)
_g.add_node("finalize", finalize_telemetry)

_g.add_edge(START, "check_telemetry")
_g.add_edge("check_telemetry", "mining_cycle")
_g.add_edge("mining_cycle", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
