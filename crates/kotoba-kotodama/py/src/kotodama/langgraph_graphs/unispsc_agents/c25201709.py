# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201709"
UNISPSC_TITLE = "Aircraft Sensor"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201709"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Bespoke fields for Aircraft Sensor domain
    sensor_model: str
    calibration_status: str
    is_redundant: bool
    telemetry_packet: dict[str, Any]


def validate_sensor_state(state: State) -> dict[str, Any]:
    """Validates the initial input for sensor parameters and redundancy configuration."""
    inp = state.get("input") or {}
    model = inp.get("model", "AS-X1-PRO")
    return {
        "log": [f"{UNISPSC_CODE}:validate_sensor_state"],
        "sensor_model": model,
        "is_redundant": inp.get("redundant", True),
    }


def calibrate_sensor(state: State) -> dict[str, Any]:
    """Simulates internal calibration logic for the specific aircraft sensor model."""
    model = state.get("sensor_model", "generic")
    # Simulation: High-end models have better calibration stability
    status = "CALIBRATED" if "PRO" in model else "DEGRADED"
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_sensor"],
        "calibration_status": status,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Processes raw data into a flight-ready telemetry packet for the avionics bus."""
    inp = state.get("input") or {}
    raw_data = inp.get("data", {})

    packet = {
        "timestamp": raw_data.get("ts", 1716470400),
        "readings": raw_data.get("readings", [101.3, 101.4]),
        "model": state.get("sensor_model"),
        "status": state.get("calibration_status")
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "telemetry_packet": packet,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": packet,
            "integrity_check": state.get("calibration_status") == "CALIBRATED",
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_sensor_state)
_g.add_node("calibrate", calibrate_sensor)
_g.add_node("telemetry", generate_telemetry)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calibrate")
_g.add_edge("calibrate", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
