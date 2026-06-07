from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    equipment_id: str
    safety_check: bool
    compliance_verified: bool

def validate_medical_grade(state: ProcurementState):
    # Simulate load test and certification protocol
    return {"compliance_verified": True}

def approve_procurement(state: ProcurementState):
    return {"safety_check": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_medical_grade)
graph.add_node("approve", approve_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
