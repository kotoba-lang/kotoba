from typing import TypedDict
from langgraph.graph import StateGraph, END

class ScintillationState(TypedDict):
    calibration_status: bool
    compliance_checked: bool
    export_license_required: bool

def validate_certification(state: ScintillationState):
    return {"compliance_checked": True} if state.get("calibration_status") else {"compliance_checked": False}

def check_export_controls(state: ScintillationState):
    return {"export_license_required": True}

graph = StateGraph(ScintillationState)
graph.add_node("validate_cert", validate_certification)
graph.add_node("export_check", check_export_controls)
graph.set_entry_point("validate_cert")
graph.add_edge("validate_cert", "export_check")
graph.add_edge("export_check", END)
graph = graph.compile()
