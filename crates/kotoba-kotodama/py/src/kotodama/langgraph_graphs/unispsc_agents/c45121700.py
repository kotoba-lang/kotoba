from typing import TypedDict
from langgraph.graph import StateGraph, END

class PhotoProcessState(TypedDict):
    equipment_id: str
    chemical_safety_pass: bool
    is_calibrated: bool

def validate_chemical_safety(state: PhotoProcessState):
    # Simulate safety protocol check
    return {"chemical_safety_pass": True} if state.get("equipment_id") else {"chemical_safety_pass": False}

def calibrate_machinery(state: PhotoProcessState):
    # Simulate hardware calibration logic
    return {"is_calibrated": True}

graph = StateGraph(PhotoProcessState)
graph.add_node("safety_check", validate_chemical_safety)
graph.add_node("calibration", calibrate_machinery)
graph.add_edge("safety_check", "calibration")
graph.add_edge("calibration", END)
graph.set_entry_point("safety_check")
graph = graph.compile()
