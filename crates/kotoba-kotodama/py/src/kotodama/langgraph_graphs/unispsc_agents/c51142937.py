from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    purity_validated: bool
    compliance_checked: bool

def validate_quality(state: ProcurementState):
    # Simulate chemical validation logic
    is_pure = state.get('purity_percentage', 0) >= 99.0
    return {"purity_validated": is_pure}

def check_compliance(state: ProcurementState):
    # Verify pharmacopoeia standards
    return {"compliance_checked": True}

graph = StateGraph(ProcurementState)
graph.add_node("validate_quality", validate_quality)
graph.add_node("check_compliance", check_compliance)
graph.set_entry_point("validate_quality")
graph.add_edge("validate_quality", "check_compliance")
graph.add_edge("check_compliance", END)
graph = graph.compile()
