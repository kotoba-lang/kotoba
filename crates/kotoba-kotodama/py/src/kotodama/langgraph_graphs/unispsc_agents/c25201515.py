# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25201515 — Lift Fan (segment 25).

Bespoke graph logic for lift fan mechanical inspection and airflow calibration.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25201515"
UNISPSC_TITLE = "Lift Fan"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25201515"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    blade_integrity_verified: bool
    airflow_cfm: float
    rotational_speed_rpm: int
    vibration_alert: bool


def inspect_system(state: State) -> dict[str, Any]:
    """Inspects the mechanical integrity of the lift fan blades and mounting."""
    inp = state.get("input") or {}
    requested_rpm = inp.get("target_rpm", 0)
    # Simulate a successful integrity check
    return {
        "log": [f"{UNISPSC_CODE}:inspect_system"],
        "blade_integrity_verified": True,
        "rotational_speed_rpm": requested_rpm,
    }


def calibrate_airflow(state: State) -> dict[str, Any]:
    """Calculates the expected airflow (CFM) based on current RPM settings."""
    rpm = state.get("rotational_speed_rpm", 0)
    # Simulation logic: Airflow is roughly 1.4 CFM per RPM for this fan model
    calculated_cfm = rpm * 1.4
    # Detect vibration risk if RPM exceeds a safety threshold
    vibration_risk = rpm > 4500
    return {
        "log": [f"{UNISPSC_CODE}:calibrate_airflow"],
        "airflow_cfm": round(calculated_cfm, 2),
        "vibration_alert": vibration_risk,
    }


def generate_telemetry(state: State) -> dict[str, Any]:
    """Generates the final telemetry packet and operational status."""
    v_alert = state.get("vibration_alert", False)
    status = "WARNING" if v_alert else "NORMAL"

    return {
        "log": [f"{UNISPSC_CODE}:generate_telemetry"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": status,
            "metrics": {
                "airflow": f"{state.get('airflow_cfm', 0.0)} CFM",
                "rpm": state.get("rotational_speed_rpm", 0),
                "integrity": "PASS" if state.get("blade_integrity_verified") else "FAIL",
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("inspect", inspect_system)
_g.add_node("calibrate", calibrate_airflow)
_g.add_node("telemetry", generate_telemetry)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "calibrate")
_g.add_edge("calibrate", "telemetry")
_g.add_edge("telemetry", END)

graph = _g.compile()
