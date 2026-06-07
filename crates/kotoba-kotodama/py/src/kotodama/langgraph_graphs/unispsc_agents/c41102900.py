from typing import TypedDict
from langgraph.graph import StateGraph, END
class HistologyState(TypedDict):
    equipment_id: str
    compliance_check: bool
    calibration_status: bool
def validate_equipment(state: HistologyState):
    return {"compliance_check": True}
def verify_calibration(state: HistologyState):
    return {"calibration_status": True}
graph = StateGraph(HistologyState)
graph.add_node("validate", validate_equipment)
graph.add_node("calibrate", verify_calibration)
graph.set_entry_point("validate")
graph.add_edge("validate", "calibrate")
graph.add_edge("calibrate", END)
graph = graph.compile()
