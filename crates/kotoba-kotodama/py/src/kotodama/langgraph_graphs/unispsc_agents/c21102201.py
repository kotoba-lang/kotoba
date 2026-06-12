# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21102201 — Pump (segment 21).

Bespoke graph logic for industrial pump monitoring, operational simulation,
and telemetry reporting. This agent handles pressure thresholds, flow rates,
and maintenance status flags for fluid handling systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21102201"
UNISPSC_TITLE = "Pump"
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21102201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    pressure_psi: float
    flow_rate_gpm: float
    valve_status: str
    maintenance_needed: bool


def initialize_pump(state: State) -> dict[str, Any]:
    """Validates input parameters and initializes pump state."""
    inp = state.get("input") or {}
    pressure = float(inp.get("target_pressure", 45.0))
    flow = float(inp.get("target_flow", 12.5))

    return {
        "log": [f"{UNISPSC_CODE}:initialize_pump -> pressure={pressure}, flow={flow}"],
        "pressure_psi": pressure,
        "flow_rate_gpm": flow,
        "valve_status": "initializing",
        "maintenance_needed": False,
    }


def monitor_performance(state: State) -> dict[str, Any]:
    """Simulates pump operation and monitors for over-pressure conditions."""
    pressure = state.get("pressure_psi", 0.0)
    flow = state.get("flow_rate_gpm", 0.0)

    # Alert if pressure exceeds safe industrial operating limits
    needs_maint = pressure > 150.0
    status = "open" if flow > 0 else "closed"

    return {
        "log": [f"{UNISPSC_CODE}:monitor_performance -> status={status}, maintenance={needs_maint}"],
        "valve_status": status,
        "maintenance_needed": needs_maint,
    }


def dispatch_telemetry(state: State) -> dict[str, Any]:
    """Formats the final operational telemetry and results for the consumer."""
    return {
        "log": [f"{UNISPSC_CODE}:dispatch_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "pressure_psi": state.get("pressure_psi"),
                "flow_rate_gpm": state.get("flow_rate_gpm"),
                "valve_status": state.get("valve_status"),
                "maintenance_needed": state.get("maintenance_needed"),
            },
            "ok": not state.get("maintenance_needed", False),
        },
    }


_g = StateGraph(State)

_g.add_node("initialize", initialize_pump)
_g.add_node("monitor", monitor_performance)
_g.add_node("dispatch", dispatch_telemetry)

_g.add_edge(START, "initialize")
_g.add_edge("initialize", "monitor")
_g.add_edge("monitor", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
