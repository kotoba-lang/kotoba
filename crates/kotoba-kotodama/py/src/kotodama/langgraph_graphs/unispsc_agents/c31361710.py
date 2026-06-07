from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    assembly_id: str
    material_certified: bool
    nit_report_passed: bool
    is_cleared_for_shipment: bool

def validate_materials(state: AssemblyState):
    # Simulate material grade verification
    return {"material_certified": True}

def perform_ndt_check(state: AssemblyState):
    # Simulate Non-Destructive Testing logic
    return {"nit_report_passed": True}

def determine_clearance(state: AssemblyState):
    cleared = state["material_certified"] and state["nit_report_passed"]
    return {"is_cleared_for_shipment": cleared}

graph = StateGraph(AssemblyState)
graph.add_node("validate", validate_materials)
graph.add_node("ndt", perform_ndt_check)
graph.add_node("clearance", determine_clearance)
graph.set_entry_point("validate")
graph.add_edge("validate", "ndt")
graph.add_edge("ndt", "clearance")
graph.add_edge("clearance", END)
graph = graph.compile()
