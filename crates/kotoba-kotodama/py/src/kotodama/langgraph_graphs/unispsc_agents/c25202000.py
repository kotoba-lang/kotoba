# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202000 — Aircraft Power (segment 25).

Bespoke graph logic for managing aircraft power systems, encompassing
generation, distribution, and monitoring of electrical loads.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202000"
UNISPSC_TITLE = "Aircraft Power"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Aircraft Power
    bus_voltage: float
    total_load_kva: float
    active_source: str
    thermal_condition: str
    safety_interlock_engaged: bool


def validate_power_source(state: State) -> dict[str, Any]:
    """Analyzes the primary power source and bus voltage levels."""
    inp = state.get("input") or {}
    source = inp.get("source", "Main Engine Generator 1")
    voltage = float(inp.get("bus_voltage", 115.0))

    # Typical aircraft standards: 115V AC or 28V DC
    interlock = voltage >= 24.0

    return {
        "log": [f"{UNISPSC_CODE}:validate_power_source {source} @ {voltage}V"],
        "active_source": source,
        "bus_voltage": voltage,
        "safety_interlock_engaged": interlock,
    }


def assess_thermal_load(state: State) -> dict[str, Any]:
    """Calculates load requirements and evaluates thermal dissipation."""
    inp = state.get("input") or {}
    load = float(inp.get("load_kva", 45.5))
    temp = inp.get("temp_c", 35.0)

    condition = "nominal" if temp < 75.0 else "critical"

    return {
        "log": [f"{UNISPSC_CODE}:assess_thermal_load {load}kVA at {temp}C"],
        "total_load_kva": load,
        "thermal_condition": condition,
    }


def dispatch_power(state: State) -> dict[str, Any]:
    """Finalizes power distribution logic based on safety and thermal checks."""
    safe = state.get("safety_interlock_engaged", False)
    condition = state.get("thermal_condition", "unknown")

    operational = safe and condition == "nominal"

    return {
        "log": [f"{UNISPSC_CODE}:dispatch_power operational={operational}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "power_on": operational,
            "active_bus": state.get("active_source"),
            "diagnostics": {
                "voltage": state.get("bus_voltage"),
                "thermal": condition
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_power_source)
_g.add_node("assess", assess_thermal_load)
_g.add_node("dispatch", dispatch_power)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "dispatch")
_g.add_edge("dispatch", END)

graph = _g.compile()
