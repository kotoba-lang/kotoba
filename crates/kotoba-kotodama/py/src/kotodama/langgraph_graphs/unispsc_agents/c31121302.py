from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    material_certified: bool
    dimensional_check_passed: bool
    nda_certified_supplier: bool

def validate_material(state: CastState):
    return {"material_certified": True}

def validate_dimensions(state: CastState):
    return {"dimensional_check_passed": True}

graph = StateGraph(CastState)
graph.add_node("material", validate_material)
graph.add_node("dimensions", validate_dimensions)
graph.set_entry_point("material")
graph.add_edge("material", "dimensions")
graph.add_edge("dimensions", END)
graph = graph.compile()
