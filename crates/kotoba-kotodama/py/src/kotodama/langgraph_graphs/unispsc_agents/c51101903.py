from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity_check: bool
    compliance_verified: bool
    approval_status: str

def validate_api_purity(state: ProcurementState):
    return {"purity_check": True}

def check_regulatory_compliance(state: ProcurementState):
    return {"compliance_verified": True}

def finalize_order(state: ProcurementState):
    return {"approval_status": "APPROVED"}

graph = StateGraph(ProcurementState)
graph.add_node("purity", validate_api_purity)
graph.add_node("compliance", check_regulatory_compliance)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("purity")
graph.add_edge("purity", "compliance")
graph.add_edge("compliance", "finalize")
graph.add_edge("finalize", END)

graph = graph.compile()
