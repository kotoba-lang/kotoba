from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_type: str
    purity_check: bool
    dimensional_analysis: bool
    passed: bool

def validate_material(state: ForgingState):
    return {"purity_check": state.get("material_type") == "lead"}

def validate_dimensions(state: ForgingState):
    return {"dimensional_analysis": True}

graph = StateGraph(ForgingState)
graph.add_node("purity_check", validate_material)
graph.add_node("dim_check", validate_dimensions)
graph.set_entry_point("purity_check")
graph.add_edge("purity_check", "dim_check")
graph.add_edge("dim_check", END)
graph = graph.compile()
