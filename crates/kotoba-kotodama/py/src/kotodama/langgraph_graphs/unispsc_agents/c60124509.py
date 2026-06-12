from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class VehicleSetState(TypedDict):
    item_name: str
    spec_check: bool
    safety_compliance: bool

def validate_materials(state: VehicleSetState):
    return {"spec_check": True}

def check_safety(state: VehicleSetState):
    return {"safety_compliance": True}

graph = StateGraph(VehicleSetState)
graph.add_node("validate", validate_materials)
graph.add_node("safety", check_safety)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
