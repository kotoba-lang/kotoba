# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122605 — Sensor Process (segment 20).

Bespoke LangGraph implementation for processing sensor data streams,
handling signal validation, digital filtering, and anomaly detection.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122605"
UNISPSC_TITLE = "Sensor Process"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122605"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Sensor Process
    sensor_id: str
    raw_stream: list[float]
    filtered_stream: list[float]
    anomaly_detected: bool
    sample_rate_hz: float


def ingest_sensor_data(state: State) -> dict[str, Any]:
    """Validates the incoming sensor payload and initializes processing state."""
    inp = state.get("input") or {}
    data = inp.get("data", [])
    sid = inp.get("sensor_id", "unknown-000")
    rate = inp.get("sample_rate", 10.0)

    return {
        "log": [f"{UNISPSC_CODE}:ingest_sensor_data:{sid}"],
        "sensor_id": sid,
        "raw_stream": data,
        "sample_rate_hz": rate,
    }


def filter_signal(state: State) -> dict[str, Any]:
    """Applies a basic digital filter (moving average) to the raw stream."""
    raw = state.get("raw_stream") or []
    # Simple 3-point moving average as a placeholder for DSP
    filtered = []
    if len(raw) >= 3:
        for i in range(len(raw) - 2):
            avg = sum(raw[i:i+3]) / 3.0
            filtered.append(round(avg, 4))
    else:
        filtered = list(raw)

    return {
        "log": [f"{UNISPSC_CODE}:filter_signal:len={len(filtered)}"],
        "filtered_stream": filtered,
    }


def analyze_anomalies(state: State) -> dict[str, Any]:
    """Checks the filtered signal against operational thresholds."""
    filtered = state.get("filtered_stream") or []
    threshold = 100.0  # Dummy threshold
    anomaly = any(v > threshold for v in filtered)

    return {
        "log": [f"{UNISPSC_CODE}:analyze_anomalies:detected={anomaly}"],
        "anomaly_detected": anomaly,
        "result": {
            "sensor_id": state.get("sensor_id"),
            "status": "ALARM" if anomaly else "OK",
            "mean_value": sum(filtered) / len(filtered) if filtered else 0,
            "metadata": {
                "code": UNISPSC_CODE,
                "title": UNISPSC_TITLE,
                "did": UNISPSC_DID
            }
        }
    }


_g = StateGraph(State)

_g.add_node("ingest", ingest_sensor_data)
_g.add_node("filter", filter_signal)
_g.add_node("analyze", analyze_anomalies)

_g.add_edge(START, "ingest")
_g.add_edge("ingest", "filter")
_g.add_edge("filter", "analyze")
_g.add_edge("analyze", END)

graph = _g.compile()
