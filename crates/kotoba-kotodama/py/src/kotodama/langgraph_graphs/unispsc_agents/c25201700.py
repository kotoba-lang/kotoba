# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201700 — Flight Comm (segment 25).

Bespoke logic for flight communication systems, handling signal validation,
link establishment, and telemetry transmission for aviation assets.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201700"
UNISPSC_TITLE = "Flight Comm"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra domain fields for Flight Comm
    signal_strength: float
    frequency_mhz: float
    encryption_status: str
    link_integrity: float


def validate_signal(state: State) -> dict[str, Any]:
    """Node: Validate frequency allocation and initial signal strength."""
    inp = state.get("input") or {}
    freq = float(inp.get("frequency", 121.5))  # Default emergency frequency
    strength = float(inp.get("strength", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_signal freq={freq}mhz strength={strength}"],
        "frequency_mhz": freq,
        "signal_strength": strength,
    }


def establish_link(state: State) -> dict[str, Any]:
    """Node: Compute link integrity and check encryption requirements."""
    strength = state.get("signal_strength", 0.0)
    freq = state.get("frequency_mhz", 0.0)

    integrity = min(1.0, strength * 1.2)
    encryption = "SECURE" if freq > 400.0 else "CLEAR"

    return {
        "log": [f"{UNISPSC_CODE}:establish_link integrity={integrity} enc={encryption}"],
        "link_integrity": integrity,
        "encryption_status": encryption,
    }


def transmit_telemetry(state: State) -> dict[str, Any]:
    """Node: Transmit telemetry package if link integrity is sufficient."""
    integrity = state.get("link_integrity", 0.0)
    success = integrity > 0.7

    return {
        "log": [f"{UNISPSC_CODE}:transmit_telemetry success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry_status": "STABLE" if success else "DROPPED",
            "integrity_metric": integrity,
            "ok": success,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_signal", validate_signal)
_g.add_node("establish_link", establish_link)
_g.add_node("transmit_telemetry", transmit_telemetry)

_g.add_edge(START, "validate_signal")
_g.add_edge("validate_signal", "establish_link")
_g.add_edge("establish_link", "transmit_telemetry")
_g.add_edge("transmit_telemetry", END)

graph = _g.compile()
