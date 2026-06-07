from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalXRayState(TypedDict):
    model_number: str
    compliance_docs: bool
    is_calibrated: bool

def validate_compliance(state: DentalXRayState):
    return {"compliance_docs": True} if state.get("model_number") else {"compliance_docs": False}

def verify_calibration(state: DentalXRayState):
    return {"is_calibrated": True}

graph = StateGraph(DentalXRayState)
graph.add_node("validate", validate_compliance)
graph.add_node("calibrate", verify_calibration)
graph.set_entry_point("validate")
graph.add_edge("validate", "calibrate")
graph.add_edge("calibrate", END)
graph = graph.compile()
