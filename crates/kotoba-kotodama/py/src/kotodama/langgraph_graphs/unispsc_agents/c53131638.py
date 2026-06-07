from typing import TypedDict
from langgraph.graph import StateGraph, END

class NailPolishState(TypedDict):
    product_name: str
    sds_verified: bool
    flammability_passed: bool

def validate_safety(state: NailPolishState):
    return {"sds_verified": True, "flammability_passed": True}

def approve_procurement(state: NailPolishState):
    return {"status": "ready_for_purchase"}

graph = StateGraph(NailPolishState)
graph.add_node("safety_check", validate_safety)
graph.add_node("approval", approve_procurement)
graph.add_edge("safety_check", "approval")
graph.add_edge("approval", END)
graph.set_entry_point("safety_check")
graph = graph.compile()
