from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class WeldingProcurementState(TypedDict):
    items: List[str]
    compliance_checked: bool
    safety_approved: bool

def validate_welding_specs(state: WeldingProcurementState):
    # Simulate validation logic for welding accessories
    return {"compliance_checked": True}

def safety_gate(state: WeldingProcurementState):
    # Logic for checking safety certifications
    return {"safety_approved": True}

graph = StateGraph(WeldingProcurementState)
graph.add_node("validate", validate_welding_specs)
graph.add_node("safety", safety_gate)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
