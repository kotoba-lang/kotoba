from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    api_name: str
    purity_check: bool
    compliance_validated: bool

def validate_purity(state: ProcurementState):
    return {"purity_check": True}

def validate_compliance(state: ProcurementState):
    return {"compliance_validated": True}

graph_builder = StateGraph(ProcurementState)
graph_builder.add_node("validate_purity", validate_purity)
graph_builder.add_node("validate_compliance", validate_compliance)
graph_builder.set_entry_point("validate_purity")
graph_builder.add_edge("validate_purity", "validate_compliance")
graph_builder.add_edge("validate_compliance", END)
graph = graph_builder.compile()
