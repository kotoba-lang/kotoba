# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122304 — Sensor (segment 20).

This module implements a bespoke LangGraph for sensor data processing,
including calibration, signal sampling, and telemetry synthesis.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122304"
UNISPSC_TITLE = "Sensor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122304"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Sensor
    sampling_rate_hz: int
    calibration_vector: list[float]
    signal_noise_ratio: float
    threshold_exceeded: bool
    firmware_version: str


def calibrate_sensor(state: State) -> dict[str, Any]:
    """Node to calibrate the sensor hardware abstraction."""
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_sensor"],
        "calibration_vector": [1.02, -0.01, 0.005],
        "signal_noise_ratio": 48.2,
        "firmware_version": "v2.4.1-stable",
    }


def sample_signal(state: State) -> dict[str, Any]:
    """Node to simulate high-frequency signal sampling and analysis."""
    inp = state.get("input") or {}
    requested_rate = inp.get("rate", 1000)

    # Simulate a threshold check based on sampling rate or input data
    is_high_load = requested_rate > 2000

    return {
        "log": [f"{UNISPSC_CODE}:sample_signal"],
        "sampling_rate_hz": requested_rate,
        "threshold_exceeded": is_high_load,
    }


def synthesize_telemetry(state: State) -> dict[str, Any]:
    """Node to compile the final telemetry packet for emission."""
    status = "nominal"
    if state.get("threshold_exceeded"):
        status = "alert"

    return {
        "log": [f"{UNISPSC_CODE}:synthesize_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "payload": {
                "status": status,
                "metrics": {
                    "hz": state.get("sampling_rate_hz"),
                    "snr_db": state.get("signal_noise_ratio"),
                },
                "metadata": {
                    "fw": state.get("firmware_version"),
                    "cal": state.get("calibration_vector"),
                }
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("calibrate", calibrate_sensor)
_g.add_node("sample", sample_signal)
_g.add_node("emit", synthesize_telemetry)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "sample")
_g.add_edge("sample", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
