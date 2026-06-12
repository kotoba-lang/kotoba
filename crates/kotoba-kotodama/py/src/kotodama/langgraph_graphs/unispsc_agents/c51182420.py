from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    purity_check: bool
    compliance_verified: bool

def validate_purity(state: ProcurementState):
    return {"purity_check": True}

def verify_compliance(state: ProcurementState):
    return {"compliance_verified": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", verify_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
