from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    quality_verified: bool
    compliance_checked: bool

def check_gmp(state: PharmState):
    return {"compliance_checked": True}

def verify_purity(state: PharmState):
    return {"quality_verified": True}

graph = StateGraph(PharmState)
graph.add_node("check_gmp", check_gmp)
graph.add_node("verify_purity", verify_purity)
graph.set_entry_point("check_gmp")
graph.add_edge("check_gmp", "verify_purity")
graph.add_edge("verify_purity", END)
graph = graph.compile()
