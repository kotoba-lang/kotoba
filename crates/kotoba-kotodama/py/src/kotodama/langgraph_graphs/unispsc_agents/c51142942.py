from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    purity_check: bool
    safety_clearance: bool

def validate_purity(state: ProcurementState):
    # Simulate chemical verification logic
    return {"purity_check": True}

def check_regulatory_compliance(state: ProcurementState):
    # Simulate regulatory/license verification
    return {"safety_clearance": True}

graph = StateGraph(ProcurementState)
graph.add_node("purity_analysis", validate_purity)
graph.add_node("regulatory_check", check_regulatory_compliance)
graph.set_entry_point("purity_analysis")
graph.add_edge("purity_analysis", "regulatory_check")
graph.add_edge("regulatory_check", END)
graph = graph.compile()
