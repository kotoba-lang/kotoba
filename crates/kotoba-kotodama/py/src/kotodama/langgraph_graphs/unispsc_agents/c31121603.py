from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    part_id: str
    material_certified: bool
    dimensional_check_passed: bool
    ndt_results: str

def validate_material(state: CastState):
    return {"material_certified": True}

def validate_dimensions(state: CastState):
    return {"dimensional_check_passed": True}

def check_ndt(state: CastState):
    return {"ndt_results": "Certified"}

graph = StateGraph(CastState)
graph.add_node("validate_material", validate_material)
graph.add_node("validate_dimensions", validate_dimensions)
graph.add_node("check_ndt", check_ndt)
graph.set_entry_point("validate_material")
graph.add_edge("validate_material", "validate_dimensions")
graph.add_edge("validate_dimensions", "check_ndt")
graph.add_edge("check_ndt", END)
graph = graph.compile()
