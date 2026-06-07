from typing import TypedDict
from langgraph.graph import StateGraph, END

class PediatricSystemState(TypedDict):
    device_id: str
    safety_check_passed: bool
    calibrated: bool
    final_approval: bool

def validate_safety_protocols(state: PediatricSystemState):
    # Simulate multi-layer safety check for pediatric restraint systems
    return {"safety_check_passed": True}

def perform_calibration(state: PediatricSystemState):
    # Simulate sensor accuracy validation for measurement systems
    return {"calibrated": True}

def finalize_specs(state: PediatricSystemState):
    # Final review for procurement compliance
    return {"final_approval": state["safety_check_passed"] and state["calibrated"]}

graph = StateGraph(PediatricSystemState)
graph.add_node("validate", validate_safety_protocols)
graph.add_node("calibrate", perform_calibration)
graph.add_node("approve", finalize_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", "calibrate")
graph.add_edge("calibrate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
