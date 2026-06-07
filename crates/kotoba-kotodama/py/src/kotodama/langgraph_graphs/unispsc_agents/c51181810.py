from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity_check: bool
    compliance_verified: bool
    final_approval: bool

def validate_purity(state: ProcurementState):
    return {"purity_check": True}

def check_compliance(state: ProcurementState):
    return {"compliance_verified": True}

def finalize_order(state: ProcurementState):
    return {"final_approval": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_compliance)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
