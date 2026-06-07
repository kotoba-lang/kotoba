from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_validated: bool

def validate_purity(state: ProcurementState):
    return {"purity_check": True}

def check_regulations(state: ProcurementState):
    return {"compliance_validated": True}

graph = StateGraph(ProcurementState)
graph.add_node("purity", validate_purity)
graph.add_node("compliance", check_regulations)
graph.add_edge("purity", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("purity")
graph = graph.compile()
