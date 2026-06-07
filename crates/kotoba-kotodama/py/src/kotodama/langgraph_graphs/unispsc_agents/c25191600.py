# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25191600 — Space Support (segment 25).

Bespoke logic for space support services, including mission validation,
telemetry monitoring, and ground station coordination.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191600"
UNISPSC_TITLE = "Space Support"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191600"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    launch_window_open: bool
    telemetry_status: str
    payload_clearance: bool
    ground_station_id: str


def validate_mission(state: State) -> dict[str, Any]:
    """Validates the mission parameters and checks payload clearance."""
    inp = state.get("input") or {}
    mission_id = inp.get("mission_id", "ST-42")
    clearance = inp.get("payload_type") != "hazardous"

    return {
        "log": [f"{UNISPSC_CODE}:validate_mission:{mission_id}"],
        "payload_clearance": clearance,
        "launch_window_open": inp.get("window_ready", True)
    }


def monitor_telemetry(state: State) -> dict[str, Any]:
    """Simulates real-time telemetry monitoring for the space vehicle."""
    is_clear = state.get("payload_clearance", False)
    status = "nominal" if is_clear else "degraded"
    station = state.get("input", {}).get("station_id", "GS-X1")

    return {
        "log": [f"{UNISPSC_CODE}:monitor_telemetry:status={status}"],
        "telemetry_status": status,
        "ground_station_id": station
    }


def finalize_support(state: State) -> dict[str, Any]:
    """Finalizes the support cycle and emits the mission report."""
    status = state.get("telemetry_status", "unknown")
    ready = state.get("launch_window_open", False)

    success = (status == "nominal" and ready)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_support:success={success}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "mission_status": "READY" if success else "HOLD",
            "telemetry": status,
            "station": state.get("ground_station_id"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate_mission", validate_mission)
_g.add_node("monitor_telemetry", monitor_telemetry)
_g.add_node("finalize_support", finalize_support)

_g.add_edge(START, "validate_mission")
_g.add_edge("validate_mission", "monitor_telemetry")
_g.add_edge("monitor_telemetry", "finalize_support")
_g.add_edge("finalize_support", END)

graph = _g.compile()
