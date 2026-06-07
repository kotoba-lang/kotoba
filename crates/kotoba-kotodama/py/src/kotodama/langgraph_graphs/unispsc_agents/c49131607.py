from typing import TypedDict
from langgraph.graph import StateGraph, END

class GunBarrelState(TypedDict):
    spec_data: dict
    compliance_passed: bool
    final_approval: bool

def validate_materials(state: GunBarrelState):
    # logic to inspect metallurgical test reports
    return {"compliance_passed": True}

def check_export_controls(state: GunBarrelState):
    # logic to perform ITAR/EAR screening
    return {"final_approval": True}

graph = StateGraph(GunBarrelState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("check_controls", check_export_controls)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "check_controls")
graph.add_edge("check_controls", END)
graph = graph.compile()
