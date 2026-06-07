from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    safety_check_passed: bool
    compliance_validated: bool

def validate_safety(state: ProcurementState):
    # Simulate safety and compliance check for therapeutic materials
    state["safety_check_passed"] = True
    return state

def validate_compliance(state: ProcurementState):
    # Check if materials meet clinical hazard regulations
    state["compliance_validated"] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node("safety_check", validate_safety)
graph.add_node("compliance_check", validate_compliance)
graph.set_entry_point("safety_check")
graph.add_edge("safety_check", "compliance_check")
graph.add_edge("compliance_check", END)
graph = graph.compile()
