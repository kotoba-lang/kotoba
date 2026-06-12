# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25202102 — Aerospace (segment 25).

Bespoke graph logic for aerospace systems management, including flight
clearance, telemetry validation, and mission objective tracking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25202102"
UNISPSC_TITLE = "Aerospace"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25202102"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Aerospace domain state
    mission_id: str
    flight_clearance_status: str
    avionics_calibration_log: list[str]
    payload_weight_kg: float
    orbital_parameters: dict[str, float]


def initiate_mission(state: State) -> dict[str, Any]:
    """Initializes the aerospace mission profile and assigns a tracking ID."""
    inp = state.get("input") or {}
    mission_id = inp.get("mission_id", "ALPHA-01")
    payload_weight = float(inp.get("payload_weight", 0.0))

    return {
        "log": [f"{UNISPSC_CODE}:initiate_mission"],
        "mission_id": mission_id,
        "payload_weight_kg": payload_weight,
        "flight_clearance_status": "PENDING",
    }


def verify_compliance(state: State) -> dict[str, Any]:
    """Checks avionics systems and verifies airworthiness compliance."""
    # Simulating a system calibration check
    calibrations = ["IMU_01:OK", "GPS_01:LOCKED", "STAR_TRACKER:SYNCED"]

    return {
        "log": [f"{UNISPSC_CODE}:verify_compliance"],
        "avionics_calibration_log": calibrations,
        "flight_clearance_status": "CLEARED" if state.get("payload_weight_kg", 0) < 50000 else "REJECTED_OVERWEIGHT",
    }


def finalize_telemetry(state: State) -> dict[str, Any]:
    """Finalizes mission parameters and prepares the result payload."""
    status = state.get("flight_clearance_status", "UNKNOWN")
    mission_id = state.get("mission_id", "N/A")

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "mission_id": mission_id,
        "status": status,
        "ok": status == "CLEARED",
    }

    return {
        "log": [f"{UNISPSC_CODE}:finalize_telemetry"],
        "result": res,
        "orbital_parameters": {"perigee": 300.0, "apogee": 300.0, "inclination": 51.6},
    }


_g = StateGraph(State)
_g.add_node("initiate_mission", initiate_mission)
_g.add_node("verify_compliance", verify_compliance)
_g.add_node("finalize_telemetry", finalize_telemetry)

_g.add_edge(START, "initiate_mission")
_g.add_edge("initiate_mission", "verify_compliance")
_g.add_edge("verify_compliance", "finalize_telemetry")
_g.add_edge("finalize_telemetry", END)

graph = _g.compile()
