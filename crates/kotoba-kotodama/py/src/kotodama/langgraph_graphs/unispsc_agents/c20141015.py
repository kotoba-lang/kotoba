# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20141015"
UNISPSC_TITLE = "Actuator"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20141015"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Actuator
    rated_voltage: float
    peak_force_newtons: float
    stroke_length_mm: float
    duty_cycle_percent: int
    health_score: float


def initialize_specs(state: State) -> dict[str, Any]:
    """Sets initial specifications for the actuator based on input."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:initialize_specs"],
        "rated_voltage": float(inp.get("voltage", 24.0)),
        "peak_force_newtons": float(inp.get("force", 1200.0)),
        "stroke_length_mm": float(inp.get("stroke", 150.0)),
        "duty_cycle_percent": int(inp.get("duty_cycle", 25)),
        "health_score": 100.0,
    }


def simulate_operation(state: State) -> dict[str, Any]:
    """Simulates operation and evaluates performance metrics."""
    duty = state.get("duty_cycle_percent", 0)
    voltage = state.get("rated_voltage", 0.0)

    # Simple logic: excessive duty cycle or low voltage impacts health
    health_impact = 0.0
    if duty > 50:
        health_impact += (duty - 50) * 0.5
    if voltage < 18.0:
        health_impact += 10.0

    new_health = max(0.0, state.get("health_score", 100.0) - health_impact)

    return {
        "log": [f"{UNISPSC_CODE}:simulate_operation"],
        "health_score": new_health,
    }


def generate_report(state: State) -> dict[str, Any]:
    """Generates the final status report for the actuator agent."""
    health = state.get("health_score", 0.0)
    is_ok = health > 70.0

    return {
        "log": [f"{UNISPSC_CODE}:generate_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "ok": is_ok,
            "diagnostics": {
                "voltage": state.get("rated_voltage"),
                "force": state.get("peak_force_newtons"),
                "stroke": state.get("stroke_length_mm"),
                "duty_cycle": state.get("duty_cycle_percent"),
                "health": health,
            },
            "status": "Operational" if is_ok else "Maintenance Required",
        },
    }


_g = StateGraph(State)
_g.add_node("initialize", initialize_specs)
_g.add_node("simulate", simulate_operation)
_g.add_node("report", generate_report)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "simulate")
_g.add_edge("simulate", "report")
_g.add_edge("report", END)

graph = _g.compile()
