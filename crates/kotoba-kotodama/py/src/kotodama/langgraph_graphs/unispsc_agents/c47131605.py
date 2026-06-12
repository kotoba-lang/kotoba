from typing import TypedDict
from langgraph.graph import StateGraph, END

class CleaningToolState(TypedDict):
    material_compliance: bool
    sanitation_level: str
    approved: bool

def validate_materials(state: CleaningToolState):
    return {"material_compliance": True}

def check_sanitation(state: CleaningToolState):
    return {"sanitation_level": "food-grade" if state.get("material_compliance") else "industrial"}

def finalize_approval(state: CleaningToolState):
    return {"approved": True}

graph = StateGraph(CleaningToolState)
graph.add_node("validate", validate_materials)
graph.add_node("sanitize", check_sanitation)
graph.add_node("approve", finalize_approval)
graph.set_entry_point("validate")
graph.add_edge("validate", "sanitize")
graph.add_edge("sanitize", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
