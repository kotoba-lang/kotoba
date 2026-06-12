from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_certified: bool
    passed_ndt: bool
    spec_verified: bool

def validate_material(state: ForgingState) -> dict:
    return {"material_certified": True}

def perform_ndt(state: ForgingState) -> dict:
    return {"passed_ndt": True}

graph = StateGraph(ForgingState)
graph.add_node("check_material", validate_material)
graph.add_node("ndt_inspection", perform_ndt)
graph.add_edge("check_material", "ndt_inspection")
graph.add_edge("ndt_inspection", END)
graph.set_entry_point("check_material")
graph = graph.compile()
