from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_verified: bool
    status: str

def validate_batch(state: ProcurementState):
    return {"purity_check": True}

def verify_compliance(state: ProcurementState):
    return {"compliance_verified": True, "status": "READY_FOR_SHIPMENT"}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_batch)
graph.add_node("compliance", verify_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
