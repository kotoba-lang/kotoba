from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    material_certified: bool
    safety_checked: bool
    passed_inspection: bool

def validate_material(state: KitchenwareState):
    # Simulate material check
    return {"material_certified": True}

def perform_safety_check(state: KitchenwareState):
    # Simulate safety standard verification
    return {"safety_checked": True}

graph = StateGraph(KitchenwareState)
graph.add_node("validate", validate_material)
graph.add_node("safety", perform_safety_check)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")
graph = graph.compile()
