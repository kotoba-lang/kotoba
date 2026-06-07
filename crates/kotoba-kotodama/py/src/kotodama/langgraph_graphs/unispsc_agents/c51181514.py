from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity_check: bool
    compliance_validated: bool
    is_stored_correctly: bool

def validate_purity(state: ProcurementState) -> dict:
    return {"purity_check": True}

def check_compliance(state: ProcurementState) -> dict:
    return {"compliance_validated": True}

graph = StateGraph(ProcurementState)
graph.add_node("purity", validate_purity)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("purity")
graph.add_edge("purity", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
