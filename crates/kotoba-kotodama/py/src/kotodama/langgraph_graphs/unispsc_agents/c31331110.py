from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_number: str
    material_certified: bool
    ultrasonic_pass: bool
    export_cleared: bool

def validate_materials(state: AssemblyState):
    return {"material_certified": True}

def perform_ndt(state: AssemblyState):
    return {"ultrasonic_pass": True}

def check_compliance(state: AssemblyState):
    return {"export_cleared": True}

graph = StateGraph(AssemblyState)
graph.add_node("validate", validate_materials)
graph.add_node("ndt", perform_ndt)
graph.add_node("export", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "ndt")
graph.add_edge("ndt", "export")
graph.add_edge("export", END)
graph = graph.compile()
