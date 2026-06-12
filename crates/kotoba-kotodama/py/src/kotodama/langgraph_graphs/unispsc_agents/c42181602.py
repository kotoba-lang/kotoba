from typing import TypedDict
from langgraph.graph import StateGraph, END

class BloodPressureSpecState(TypedDict):
    device_id: str
    calibration_status: bool
    accuracy_check_passed: bool

def validate_certification(state: BloodPressureSpecState):
    return {"calibration_status": True}

def perform_accuracy_check(state: BloodPressureSpecState):
    return {"accuracy_check_passed": True}

graph = StateGraph(BloodPressureSpecState)
graph.add_node("validate_cert", validate_certification)
graph.add_node("accuracy_check", perform_accuracy_check)
graph.add_edge("validate_cert", "accuracy_check")
graph.add_edge("accuracy_check", END)
graph.set_entry_point("validate_cert")
graph = graph.compile()
