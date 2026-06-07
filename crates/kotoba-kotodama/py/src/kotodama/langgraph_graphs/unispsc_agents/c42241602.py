from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastCutterState(TypedDict):
    device_id: str
    safety_check: bool
    calibration_passed: bool

def validate_cutter(state: CastCutterState):
    return {"safety_check": True}

def perform_calibration(state: CastCutterState):
    return {"calibration_passed": True}

graph = StateGraph(CastCutterState)
graph.add_node("validate", validate_cutter)
graph.add_node("calibrate", perform_calibration)
graph.set_entry_point("validate")
graph.add_edge("validate", "calibrate")
graph.add_edge("calibrate", END)
graph = graph.compile()
