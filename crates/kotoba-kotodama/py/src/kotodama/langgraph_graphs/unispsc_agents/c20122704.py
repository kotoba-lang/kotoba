# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122704 — Sensor (segment 20).
Bespoke logic for sensor data acquisition, calibration, and telemetry formatting.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122704"
UNISPSC_TITLE = "Sensor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122704"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain specific fields for Sensor
    sensor_mode: str
    is_faulty: bool
    calibration_coefficient: float
    telemetry_buffer: list[float]


def validate_parameters(state: State) -> dict[str, Any]:
    """Validates the sensor configuration parameters from the input context."""
    inp = state.get("input") or {}
    mode = inp.get("mode", "continuous")
    # Simulation of hardware verification
    return {
        "log": [f"{UNISPSC_CODE}:validate_parameters"],
        "sensor_mode": mode,
        "is_faulty": False,
    }


def perform_calibration(state: State) -> dict[str, Any]:
    """Calculates calibration coefficients based on system baseline signals."""
    inp = state.get("input") or {}
    baseline = inp.get("baseline_signal", 0.05)
    # Apply a synthetic calibration curve
    coeff = 1.0 + (baseline * 0.15)
    return {
        "log": [f"{UNISPSC_CODE}:perform_calibration"],
        "calibration_coefficient": coeff,
    }


def capture_telemetry(state: State) -> dict[str, Any]:
    """Simulates signal sampling, applies calibration, and generates final telemetry."""
    inp = state.get("input") or {}
    raw_signals = inp.get("samples", [0.5, 0.51, 0.49])
    coeff = state.get("calibration_coefficient", 1.0)

    calibrated_signals = [s * coeff for s in raw_signals]
    avg_value = sum(calibrated_signals) / len(calibrated_signals) if calibrated_signals else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:capture_telemetry"],
        "telemetry_buffer": calibrated_signals,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "measurement": round(avg_value, 4),
            "sample_count": len(calibrated_signals),
            "mode": state.get("sensor_mode"),
            "status": "operational" if not state.get("is_faulty") else "fault",
            "unit": "standard_unit",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_parameters)
_g.add_node("calibrate", perform_calibration)
_g.add_node("capture", capture_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "capture")
_g.add_edge("capture", END)

graph = _g.compile()
