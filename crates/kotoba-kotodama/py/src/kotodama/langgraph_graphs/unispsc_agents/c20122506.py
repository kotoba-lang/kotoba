# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122506"
UNISPSC_TITLE = "Robot"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122506"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    battery_level: float
    firmware_v: str
    sensor_map: dict[str, bool]
    mission_id: str

def startup_sequence(state: State) -> dict[str, Any]:
    """Perform power-on self-test and hardware initialization."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:startup_sequence"],
        "battery_level": 99.8,
        "firmware_v": "4.2.0-stable",
        "mission_id": inp.get("mission_id", "M-INIT-001"),
        "sensor_map": {"lidar": True, "imu": True, "depth_cam": False}
    }

def execute_mission(state: State) -> dict[str, Any]:
    """Simulate navigation and task execution based on mission parameters."""
    sensors = state.get("sensor_map", {}).copy()
    sensors["depth_cam"] = True  # Simulate turning on a sensor
    return {
        "log": [f"{UNISPSC_CODE}:execute_mission"],
        "battery_level": 88.5,
        "sensor_map": sensors
    }

def shutdown_and_report(state: State) -> dict[str, Any]:
    """Park motors and prepare telemetry data for the coordinator."""
    return {
        "log": [f"{UNISPSC_CODE}:shutdown_and_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "mission_status": "COMPLETED",
            "telemetry": {
                "final_battery": state.get("battery_level"),
                "mission_id": state.get("mission_id"),
                "firmware": state.get("firmware_v"),
                "active_sensors": [k for k, v in state.get("sensor_map", {}).items() if v]
            }
        }
    }

_g = StateGraph(State)
_g.add_node("startup_sequence", startup_sequence)
_g.add_node("execute_mission", execute_mission)
_g.add_node("shutdown_and_report", shutdown_and_report)

_g.add_edge(START, "startup_sequence")
_g.add_edge("startup_sequence", "execute_mission")
_g.add_edge("execute_mission", "shutdown_and_report")
_g.add_edge("shutdown_and_report", END)

graph = _g.compile()
