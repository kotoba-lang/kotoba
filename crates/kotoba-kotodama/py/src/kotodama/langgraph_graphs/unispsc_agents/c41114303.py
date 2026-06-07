from typing import TypedDict
from langgraph.graph import StateGraph, END

class WaterLevelScannerState(TypedDict):
    device_id: str
    calibration_status: bool
    data_integrity_check: bool

def validate_sensor_calibration(state: WaterLevelScannerState):
    return {"calibration_status": state.get("calibration_status", False)}

def verify_telemetry_link(state: WaterLevelScannerState):
    return {"data_integrity_check": True}

graph = StateGraph(WaterLevelScannerState)
graph.add_node("calibrate", validate_sensor_calibration)
graph.add_node("telemetry", verify_telemetry_link)
graph.add_edge("calibrate", "telemetry")
graph.add_edge("telemetry", END)
graph.set_entry_point("calibrate")
graph = graph.compile()
