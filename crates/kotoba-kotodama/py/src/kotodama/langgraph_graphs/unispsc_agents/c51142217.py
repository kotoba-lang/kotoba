from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    api_name: str
    compliance_cleared: bool
    purity_validated: bool

def check_compliance(state: ProcurementState):
    return {"compliance_cleared": True}

def validate_purity(state: ProcurementState):
    return {"purity_validated": True}

graph_builder = StateGraph(ProcurementState)
graph_builder.add_node("compliance", check_compliance)
graph_builder.add_node("purity_check", validate_purity)
graph_builder.add_edge("compliance", "purity_check")
graph_builder.add_edge("purity_check", END)
graph_builder.set_entry_point("compliance")
graph = graph_builder.compile()
