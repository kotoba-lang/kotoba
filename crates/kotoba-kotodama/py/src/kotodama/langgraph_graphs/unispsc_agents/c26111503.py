# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111503 — Drive (segment 26).

Bespoke LangGraph implementation for power transmission drive control
and specification management.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111503"
UNISPSC_TITLE = "Drive"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111503"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Electric Motor Drives (UNISPSC 26111503)
    rated_voltage: int
    rated_power_kw: float
    frequency_range_hz: tuple[float, float]
    cooling_type: str
    control_architecture: str


def validate_power_envelope(state: State) -> dict[str, Any]:
    """Analyzes the input requirements to define the power envelope of the drive."""
    inp = state.get("input") or {}
    voltage = int(inp.get("voltage", 480))
    power = float(inp.get("power_kw", 5.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_power_envelope"],
        "rated_voltage": voltage,
        "rated_power_kw": power,
    }


def configure_drive_topology(state: State) -> dict[str, Any]:
    """Selects appropriate inverter topology and cooling based on power rating."""
    power = state.get("rated_power_kw", 0.0)

    # Industrial drives above 75kW typically require advanced cooling and architectures
    if power > 75.0:
        cooling = "Liquid-Cooled"
        arch = "Active Front End (AFE)"
    else:
        cooling = "Forced Air"
        arch = "6-Pulse Diode Bridge"

    return {
        "log": [f"{UNISPSC_CODE}:configure_drive_topology"],
        "cooling_type": cooling,
        "control_architecture": arch,
        "frequency_range_hz": (0.1, 120.0),
    }


def emit_technical_manifest(state: State) -> dict[str, Any]:
    """Compiles the final drive specification into the result state."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_technical_manifest"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "drive_manifest": {
                "voltage_class": f"{state.get('rated_voltage')}V",
                "power_class": f"{state.get('rated_power_kw')}kW",
                "cooling": state.get("cooling_type"),
                "architecture": state.get("control_architecture"),
                "operating_range": state.get("frequency_range_hz"),
            },
            "status": "ready_for_deployment",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_power_envelope)
_g.add_node("configure", configure_drive_topology)
_g.add_node("emit", emit_technical_manifest)

_g.add_edge(START, "validate")
_g.add_edge("validate", "configure")
_g.add_edge("configure", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
