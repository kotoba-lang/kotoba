from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipeSpecState(TypedDict):
    material_grade: str
    pressure_test_passed: bool
    weld_validation_status: str

def validate_materials(state: PipeSpecState):
    return {"material_grade": state.get("material_grade", "Unknown"), "weld_validation_status": "Pending"}

def perform_ndt_check(state: PipeSpecState):
    return {"weld_validation_status": "Certified" if state.get("pressure_test_passed") else "Rejected"}

graph = StateGraph(PipeSpecState)
graph.add_node("validate", validate_materials)
graph.add_node("ndt_check", perform_ndt_check)
graph.add_edge("validate", "ndt_check")
graph.add_edge("ndt_check", END)
graph.set_entry_point("validate")
graph = graph.compile()
