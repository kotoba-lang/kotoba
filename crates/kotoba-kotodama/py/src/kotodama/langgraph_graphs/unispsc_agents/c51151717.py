from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    compliance_checked: bool
    vendor_approved: bool

def validate_pharma_specs(state: ProcurementState):
    # Simulate pharmaceutical regulatory check
    return {"compliance_checked": True}

def verify_vendor_license(state: ProcurementState):
    # Simulate vendor certification validation
    return {"vendor_approved": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_pharma_specs)
graph.add_node("verify", verify_vendor_license)
graph.set_entry_point("validate")
graph.add_edge("validate", "verify")
graph.add_edge("verify", END)
graph = graph.compile()
