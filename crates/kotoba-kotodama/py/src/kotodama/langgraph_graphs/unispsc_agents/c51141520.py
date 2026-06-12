from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    license_valid: bool
    purity_level: float
    approved: bool

def validate_license(state: ProcurementState):
    # Simulate regulatory check
    return {"license_valid": True}

def check_purity(state: ProcurementState):
    # Validate pharmaceutical grade
    is_approved = state.get("purity_level", 0.0) >= 99.0
    return {"approved": is_approved}

graph = StateGraph(ProcurementState)
graph.add_node("validate_license", validate_license)
graph.add_node("check_purity", check_purity)
graph.add_edge("validate_license", "check_purity")
graph.add_edge("check_purity", END)
graph.set_entry_point("validate_license")
graph = graph.compile()
