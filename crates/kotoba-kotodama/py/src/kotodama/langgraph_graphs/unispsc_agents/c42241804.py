from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    compliance_checked: bool
    vendor_approved: bool

def validate_medical_compliance(state: ProcurementState):
    # Simulate regulatory validation for medical softgoods
    state['compliance_checked'] = True
    return state

def check_vendor_accreditation(state: ProcurementState):
    # Verify ISO 13485 certification
    state['vendor_approved'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_medical_compliance)
graph.add_node("accredit", check_vendor_accreditation)
graph.add_edge("validate", "accredit")
graph.add_edge("accredit", END)
graph.set_entry_point("validate")
graph = graph.compile()
