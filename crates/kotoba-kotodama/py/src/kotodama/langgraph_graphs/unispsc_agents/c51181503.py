from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    compliance_cleared: bool
    quality_score: float

def validate_gmp(state: ProcurementState):
    return {"compliance_cleared": True}

def check_purity(state: ProcurementState):
    return {"quality_score": 99.9}

graph = StateGraph(ProcurementState)
graph.add_node("validate_gmp", validate_gmp)
graph.add_node("check_purity", check_purity)
graph.set_entry_point("validate_gmp")
graph.add_edge("validate_gmp", "check_purity")
graph.add_edge("check_purity", END)
graph = graph.compile()
