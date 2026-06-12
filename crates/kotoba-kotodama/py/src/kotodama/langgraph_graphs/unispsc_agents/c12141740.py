from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PolymerState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    status: str

def validate_material_purity(state: PolymerState):
    # Simulate stringent lab validation
    is_pure = True
    return {"purity_check": is_pure, "status": "Purity Confirmed" if is_pure else "Rejected"}

def perform_safety_scan(state: PolymerState):
    # Simulate dual-use regulatory compliance check
    is_safe = state["purity_check"]
    return {"safety_clearance": is_safe, "status": "Cleared for R&D" if is_safe else "Flagged for Review"}

# Construct graph
graph = StateGraph(PolymerState)
graph.add_node("validate", validate_material_purity)
graph.add_node("safety", perform_safety_scan)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")

graph = graph.compile()
