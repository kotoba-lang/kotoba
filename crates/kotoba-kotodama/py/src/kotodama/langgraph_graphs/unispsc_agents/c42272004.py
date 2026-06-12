from typing import TypedDict
from langgraph.graph import StateGraph, END

class IntubationState(TypedDict):
    material: str
    sterile: bool
    compliance_score: float

def validate_materials(state: IntubationState):
    return {"compliance_score": 1.0 if state.get("material") == "malleable_alloy" else 0.5}

def check_sterilization(state: IntubationState):
    return {"sterile": True}

graph = StateGraph(IntubationState)
graph.add_node("material_check", validate_materials)
graph.add_node("sterilization_check", check_sterilization)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "sterilization_check")
graph.add_edge("sterilization_check", END)
graph = graph.compile()
