from typing import TypedDict
from langgraph.graph import StateGraph, END

class ElectrodeProcurementState(TypedDict):
    spec_compliance: bool
    safety_check_passed: bool
    product_name: str

def validate_spec(state: ElectrodeProcurementState):
    # Simulate spec validation logic for electrode gels
    return {"spec_compliance": True}

def safety_compliance_check(state: ElectrodeProcurementState):
    # Simulate regulatory check (e.g. FDA/CE compliance)
    return {"safety_check_passed": True}

graph = StateGraph(ElectrodeProcurementState)
graph.add_node("validate", validate_spec)
graph.add_node("safety", safety_compliance_check)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
