# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24101716 — Conveyor (segment 24).

Bespoke LangGraph implementation for managing material handling conveyor systems.
This agent handles load validation, speed optimization, and routing logic.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24101716"
UNISPSC_TITLE = "Conveyor"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24101716"


class State(TypedDict, total=False):
    # Required fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Conveyor machinery
    conveyor_speed: float  # m/s
    load_weight: float    # kg
    belt_tension_ok: bool
    routing_destination: str


def check_system_integrity(state: State) -> dict[str, Any]:
    """Validates the load and checks conveyor belt health parameters."""
    inp = state.get("input") or {}
    weight = float(inp.get("weight", 0.0))
    destination = str(inp.get("destination", "bin_alpha"))

    # Safety logic: excessive weight triggers tension warnings
    tension_ok = weight < 1500.0

    return {
        "log": [f"{UNISPSC_CODE}:check_system_integrity"],
        "load_weight": weight,
        "routing_destination": destination,
        "belt_tension_ok": tension_ok
    }


def calculate_throughput(state: State) -> dict[str, Any]:
    """Optimizes conveyor speed based on current load weight and safety margins."""
    weight = state.get("load_weight", 0.0)

    # Operational curve: heavier loads move slower to prevent motor strain
    if weight > 800:
        speed = 0.3
    elif weight > 200:
        speed = 0.8
    else:
        speed = 2.2

    return {
        "log": [f"{UNISPSC_CODE}:calculate_throughput"],
        "conveyor_speed": speed
    }


def finalize_dispatch(state: State) -> dict[str, Any]:
    """Finalizes the routing process and generates the operational summary."""
    integrity_ok = state.get("belt_tension_ok", False)
    speed = state.get("conveyor_speed", 0.0)
    dest = state.get("routing_destination", "unknown")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_dispatch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "status": "dispatched" if integrity_ok else "emergency_stop",
            "telemetry": {
                "velocity_ms": speed,
                "target_node": dest,
                "measured_load": state.get("load_weight")
            },
            "ok": integrity_ok
        }
    }


_g = StateGraph(State)

_g.add_node("check_system_integrity", check_system_integrity)
_g.add_node("calculate_throughput", calculate_throughput)
_g.add_node("finalize_dispatch", finalize_dispatch)

_g.add_edge(START, "check_system_integrity")
_g.add_edge("check_system_integrity", "calculate_throughput")
_g.add_edge("calculate_throughput", "finalize_dispatch")
_g.add_edge("finalize_dispatch", END)

graph = _g.compile()
