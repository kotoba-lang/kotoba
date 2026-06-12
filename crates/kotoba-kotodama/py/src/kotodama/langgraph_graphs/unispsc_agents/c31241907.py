from typing import TypedDict
from langgraph.graph import StateGraph, END

class DomeState(TypedDict):
    material_certified: bool
    tolerance_checked: bool
    status: str

def validate_materials(state: DomeState):
    return {"material_certified": True}

def check_dimensions(state: DomeState):
    return {"tolerance_checked": True, "status": "APPROVED"}

graph = StateGraph(DomeState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("check_dimensions", check_dimensions)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "check_dimensions")
graph.add_edge("check_dimensions", END)
graph = graph.compile()
