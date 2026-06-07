# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26111519 — Torque Graph (segment 26).

Bespoke graph logic for mechanical torque data processing and visualization
within the power generation and kinetic transmission segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26111519"
UNISPSC_TITLE = "Torque Graph"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26111519"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Torque Graph
    torque_samples: list[float]
    units: str
    peak_torque: float
    graph_points: list[tuple[float, float]]
    is_calibrated: bool


def ingest_telemetry(state: State) -> dict[str, Any]:
    """Validates and prepares torque telemetry data from the input payload."""
    inp = state.get("input") or {}
    raw_samples = inp.get("samples", [])
    units = inp.get("units", "Nm")

    # Ensure numeric types for processing
    samples = [float(s) for s in raw_samples if isinstance(s, (int, float))]

    return {
        "log": [f"{UNISPSC_CODE}:ingest_telemetry"],
        "torque_samples": samples,
        "units": units,
        "is_calibrated": inp.get("calibrated", True)
    }


def analyze_dynamics(state: State) -> dict[str, Any]:
    """Calculates mechanical properties and generates time-series graph points."""
    samples = state.get("torque_samples", [])
    peak = max(samples) if samples else 0.0

    # Generate graph points (index as time-step approximation)
    points = [(float(i), val) for i, val in enumerate(samples)]

    return {
        "log": [f"{UNISPSC_CODE}:analyze_dynamics"],
        "peak_torque": peak,
        "graph_points": points
    }


def finalize_graph(state: State) -> dict[str, Any]:
    """Prepares the final torque graph visualization and summary results."""
    samples = state.get("torque_samples", [])
    units = state.get("units", "Nm")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_graph"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "peak_torque": state.get("peak_torque"),
                "mean_torque": sum(samples) / len(samples) if samples else 0.0,
                "sample_count": len(samples),
                "units": units
            },
            "visualization": {
                "type": "torque_curve",
                "points": state.get("graph_points")
            },
            "status": "operational" if state.get("is_calibrated") else "uncalibrated_warning"
        },
    }


_g = StateGraph(State)
_g.add_node("ingest", ingest_telemetry)
_g.add_node("analyze", analyze_dynamics)
_g.add_node("finalize", finalize_graph)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "analyze")
_g.add_edge("analyze", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
