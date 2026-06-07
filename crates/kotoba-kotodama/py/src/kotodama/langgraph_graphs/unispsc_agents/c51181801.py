from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    purity_validated: bool
    compliance_cleared: bool

def validate_purity(state: ProcurementState):
    return {"purity_validated": True}

def check_regulatory(state: ProcurementState):
    return {"compliance_cleared": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("check_regulatory", check_regulatory)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "check_regulatory")
graph.add_edge("check_regulatory", END)
graph = graph.compile()
