from typing import TypedDict
from langgraph.graph import StateGraph, END

class GratingState(TypedDict):
    material_specs: dict
    load_tested: bool
    approved: bool

def validate_materials(state: GratingState):
    # Business logic for plastic grating material compliance
    return {"approved": state.get("material_specs", {}).get("grade") is not None}

def check_load_safety(state: GratingState):
    return {"load_tested": True}

graph = StateGraph(GratingState)
graph.add_node("validate", validate_materials)
graph.add_node("load_check", check_load_safety)
graph.set_entry_point("validate")
graph.add_edge("validate", "load_check")
graph.add_edge("load_check", END)
graph = graph.compile()
