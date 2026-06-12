from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    model_number: str
    spec_check_passed: bool
    export_license_required: bool

def validate_specs(state: RobotProcurementState):
    # Logic for ISO 10218 compliance verification
    return {"spec_check_passed": True}

def check_export_controls(state: RobotProcurementState):
    # Logic for dual-use export control screening
    return {"export_license_required": False}

graph = StateGraph(RobotProcurementState)
graph.add_node("validate", validate_specs)
graph.add_node("export_screen", check_export_controls)
graph.set_entry_point("validate")
graph.add_edge("validate", "export_screen")
graph.add_edge("export_screen", END)
graph = graph.compile()
