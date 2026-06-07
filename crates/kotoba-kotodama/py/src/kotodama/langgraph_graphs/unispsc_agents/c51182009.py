from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_validated: bool
    compliance_cleared: bool

def validate_purity(state: ProcurementState):
    return {"purity_validated": True}

def check_regulatory_compliance(state: ProcurementState):
    return {"compliance_cleared": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_regulatory_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
