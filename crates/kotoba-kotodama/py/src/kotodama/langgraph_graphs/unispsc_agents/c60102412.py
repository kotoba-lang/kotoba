from typing import TypedDict
from langgraph.graph import StateGraph, END

class PegboardState(TypedDict):
    material_certified: bool
    count_verified: bool
    safety_check: bool

def validate_materials(state: PegboardState):
    return {"material_certified": True}

def verify_quantity(state: PegboardState):
    return {"count_verified": True}

def safety_inspection(state: PegboardState):
    return {"safety_check": True}

graph = StateGraph(PegboardState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("verify_quantity", verify_quantity)
graph.add_node("safety_inspection", safety_inspection)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "verify_quantity")
graph.add_edge("verify_quantity", "safety_inspection")
graph.add_edge("safety_inspection", END)
graph = graph.compile()
