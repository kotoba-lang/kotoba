# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111916 — Rescue Signal (segment 25).

This bespoke LangGraph implementation handles the state transitions for a rescue signal
beacon, including hardware diagnostic, signal modulation, and broadcast execution.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111916"
UNISPSC_TITLE = "Rescue Signal"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111916"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    signal_mode: str
    battery_voltage: float
    carrier_frequency: float
    is_transmitting: bool


def initialize_beacon(state: State) -> dict[str, Any]:
    """Perform hardware diagnostics and determine signal mode."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "EPIRB")
    voltage = inp.get("voltage", 12.6)
    return {
        "log": [f"{UNISPSC_CODE}:initialize_beacon:mode={mode}"],
        "signal_mode": mode,
        "battery_voltage": voltage,
    }


def modulate_signal(state: State) -> dict[str, Any]:
    """Set the carrier frequency based on the signal mode."""
    mode = state.get("signal_mode", "EPIRB")
    # EPIRB typically uses 406 MHz for satellite rescue
    freq = 406.025 if mode == "EPIRB" else 121.5
    return {
        "log": [f"{UNISPSC_CODE}:modulate_signal:freq={freq}MHz"],
        "carrier_frequency": freq,
    }


def broadcast(state: State) -> dict[str, Any]:
    """Execute the final broadcast sequence and populate results."""
    voltage = state.get("battery_voltage", 0.0)
    success = voltage > 10.5
    return {
        "log": [f"{UNISPSC_CODE}:broadcast:success={success}"],
        "is_transmitting": success,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "transmission": {
                "active": success,
                "frequency": state.get("carrier_frequency"),
                "mode": state.get("signal_mode"),
            },
        },
    }


_g = StateGraph(State)
_g.add_node("initialize_beacon", initialize_beacon)
_g.add_node("modulate_signal", modulate_signal)
_g.add_node("broadcast", broadcast)

_g.add_edge(START, "initialize_beacon")
_g.add_edge("initialize_beacon", "modulate_signal")
_g.add_edge("modulate_signal", "broadcast")
_g.add_edge("broadcast", END)

graph = _g.compile()
