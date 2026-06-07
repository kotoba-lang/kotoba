# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "13101504"
UNISPSC_TITLE = "Gas Supply"
UNISPSC_SEGMENT = "13"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c13101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    gas_type: str
    flow_rate_m3h: float
    pressure_bar: float
    leak_detection_active: bool
    supply_status: str


def monitor_flow(state: State) -> dict[str, Any]:
    """Monitors the current gas flow rate and type from input sensors."""
    inp = state.get("input") or {}
    gas_type = inp.get("gas_type", "Natural Gas")
    flow = float(inp.get("flow_rate", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:monitor_flow -> {gas_type} flowing at {flow} m3/h"],
        "gas_type": gas_type,
        "flow_rate_m3h": flow,
    }


def analyze_pressure(state: State) -> dict[str, Any]:
    """Analyzes system pressure and checks for leak detection status."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure", 1.013))  # Default to 1 atm
    leaks_clear = inp.get("leak_sensors_clear", True)

    status = "STABLE" if 0.8 <= pressure <= 10.0 and leaks_clear else "CRITICAL"

    return {
        "log": [f"{UNISPSC_CODE}:analyze_pressure -> {pressure} bar, status: {status}"],
        "pressure_bar": pressure,
        "leak_detection_active": leaks_clear,
        "supply_status": status,
    }


def validate_supply_delivery(state: State) -> dict[str, Any]:
    """Validates the final supply state and prepares the actor result."""
    status = state.get("supply_status", "UNKNOWN")
    is_ok = status == "STABLE"

    return {
        "log": [f"{UNISPSC_CODE}:validate_supply_delivery -> ok={is_ok}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "gas_type": state.get("gas_type"),
            "flow_rate": state.get("flow_rate_m3h"),
            "pressure": state.get("pressure_bar"),
            "operational_status": status,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("monitor_flow", monitor_flow)
_g.add_node("analyze_pressure", analyze_pressure)
_g.add_node("validate_supply_delivery", validate_supply_delivery)

_g.add_edge(START, "monitor_flow")
_g.add_edge("monitor_flow", "analyze_pressure")
_g.add_edge("analyze_pressure", "validate_supply_delivery")
_g.add_edge("validate_supply_delivery", END)

graph = _g.compile()
