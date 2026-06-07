# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25111933 — Tide Clock (segment 25).

Bespoke graph logic for tidal cycle calculation and clock synchronization.
This implementation simulates harmonic constants to determine water levels
relative to a lunar phase for a given station ID.
"""

from __future__ import annotations

import math
from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25111933"
UNISPSC_TITLE = "Tide Clock"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25111933"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific state fields for Tide Clock
    station_id: str
    lunar_phase: float
    current_height_meters: float
    drift_correction: int


def validate_station(state: State) -> dict[str, Any]:
    """Checks for station configuration and initializes lunar tracking."""
    inp = state.get("input") or {}
    station = inp.get("station_id", "STN-DEFAULT-01")
    phase = float(inp.get("lunar_phase", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_station id={station}"],
        "station_id": station,
        "lunar_phase": phase % 1.0,
    }


def compute_tide_level(state: State) -> dict[str, Any]:
    """Calculates height based on a simplified double-diurnal harmonic model."""
    phase = state.get("lunar_phase", 0.0)
    # Simulate tides: high tides at phase 0.0, 0.5, 1.0
    # Amplitude of 2.0 meters
    height = 2.0 * math.cos(phase * 4 * math.pi)

    # Calculate drift based on phase progression (simulated)
    drift = int(phase * 50)  # minutes of lag

    return {
        "log": [f"{UNISPSC_CODE}:compute_tide_level h={height:.2f}m"],
        "current_height_meters": height,
        "drift_correction": drift,
    }


def format_clock_sync(state: State) -> dict[str, Any]:
    """Generates the final payload for the Tide Clock display hardware."""
    height = state.get("current_height_meters", 0.0)
    is_rising = height > 0

    return {
        "log": [f"{UNISPSC_CODE}:format_clock_sync h_final={height:.2f}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "payload": {
                "station": state.get("station_id"),
                "meters": round(height, 3),
                "trend": "RISING" if is_rising else "FALLING",
                "sync_offset": state.get("drift_correction", 0),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_station)
_g.add_node("compute", compute_tide_level)
_g.add_node("format", format_clock_sync)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "format")
_g.add_edge("format", END)

graph = _g.compile()
