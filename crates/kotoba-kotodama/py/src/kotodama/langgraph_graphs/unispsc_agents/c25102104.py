# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25102104 — Tractor.
Bespoke logic for heavy machinery operation and status monitoring.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25102104"
UNISPSC_TITLE = "Tractor"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25102104"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Tractor
    engine_rpm: int
    fuel_level_pct: float
    safety_interlock_active: bool
    hydraulic_system_ready: bool


def inspect_systems(state: State) -> dict[str, Any]:
    """Node to validate tractor readiness based on fuel and safety interlocks."""
    inp = state.get("input") or {}
    fuel = float(inp.get("fuel_pct", 100.0))
    safety = bool(inp.get("safety_interlock", True))

    return {
        "log": [f"{UNISPSC_CODE}:inspect_systems - Fuel at {fuel}%"],
        "fuel_level_pct": fuel,
        "safety_interlock_active": safety,
        "hydraulic_system_ready": safety and fuel > 5.0,
    }


def execute_task(state: State) -> dict[str, Any]:
    """Node to simulate tractor engine engagement and hydraulic operation."""
    ready = state.get("hydraulic_system_ready", False)
    rpm = 1800 if ready else 0

    return {
        "log": [f"{UNISPSC_CODE}:execute_task - RPM set to {rpm}"],
        "engine_rpm": rpm,
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Node to emit final status report and telemetry data."""
    rpm = state.get("engine_rpm", 0)
    fuel = state.get("fuel_level_pct", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "status": "operational" if rpm > 0 else "idling/safety_halt",
            "telemetry": {
                "engine_rpm": rpm,
                "fuel_level": fuel,
                "did": UNISPSC_DID,
            },
            "ok": rpm > 0 or fuel > 0,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect_systems", inspect_systems)
_g.add_node("execute_task", execute_task)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "inspect_systems")
_g.add_edge("inspect_systems", "execute_task")
_g.add_edge("execute_task", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
