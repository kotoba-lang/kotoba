from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    purity_validated: bool
    compliance_cleared: bool

def validate_purity(state: ProcurementState):
    # Simulate chemical assay verification
    return {"purity_validated": True}

def check_regulatory(state: ProcurementState):
    # Simulate regulatory agency check
    return {"compliance_cleared": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate_assay", validate_purity)
graph.add_node("check_regulations", check_regulatory)
graph.set_entry_point("validate_assay")
graph.add_edge("validate_assay", "check_regulations")
graph.add_edge("check_regulations", END)
graph = graph.compile()
