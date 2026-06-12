# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122708"
UNISPSC_TITLE = "Sensor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122708"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    calibration_status: str
    signal_threshold: float
    is_active: bool
    sampling_rate_hz: int
    environment_noise_floor: float

def calibrate_sensor(state: State) -> dict[str, Any]:
    """Validates sensor calibration parameters and sets operational thresholds."""
    inp = state.get("input") or {}
    threshold = inp.get("threshold", 0.75)
    noise = inp.get("noise_floor", 0.05)

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_sensor"],
        "calibration_status": "nominal",
        "signal_threshold": float(threshold),
        "environment_noise_floor": float(noise),
        "is_active": True
    }

def process_signal(state: State) -> dict[str, Any]:
    """Simulates signal acquisition and processing based on the configured rate."""
    inp = state.get("input") or {}
    requested_rate = inp.get("sampling_rate", 1000)

    # Logic to ensure sampling rate is within hardware limits
    actual_rate = min(max(requested_rate, 1), 5000)

    return {
        "log": [f"{UNISPSC_CODE}:process_signal"],
        "sampling_rate_hz": actual_rate
    }

def emit_telemetry(state: State) -> dict[str, Any]:
    """Packages the processed sensor state into a standard telemetry result."""
    return {
        "log": [f"{UNISPSC_CODE}:emit_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "telemetry": {
                "active": state.get("is_active"),
                "calibration": state.get("calibration_status"),
                "threshold": state.get("signal_threshold"),
                "noise": state.get("environment_noise_floor"),
                "rate": state.get("sampling_rate_hz")
            },
            "status": "ready"
        }
    }

_g = StateGraph(State)

_g.add_node("calibrate", calibrate_sensor)
_g.add_node("process", process_signal)
_g.add_node("emit", emit_telemetry)

_g.add_edge(START, "calibrate")
_g.add_edge("calibrate", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
