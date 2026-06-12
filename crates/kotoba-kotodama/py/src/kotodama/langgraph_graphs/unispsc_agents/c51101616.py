from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_validated: bool
    safety_clearance: bool

def validate_safety(state: ProcurementState):
    return {"safety_clearance": True}

def process_procurement(state: ProcurementState):
    return {"purity_validated": True}

graph = StateGraph(ProcurementState)
graph.add_node("safety_check", validate_safety)
graph.add_node("purity_audit", process_procurement)
graph.set_entry_point("safety_check")
graph.add_edge("safety_check", "purity_audit")
graph.add_edge("purity_audit", END)
graph = graph.compile()
