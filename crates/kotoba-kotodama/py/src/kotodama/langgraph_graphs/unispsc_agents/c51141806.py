from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    item_name: str
    compliance_valid: bool
    permits_verified: bool

def validate_compliance(state: ProcurementState):
    return {'compliance_valid': True}

def verify_regulatory_permits(state: ProcurementState):
    return {'permits_verified': True}

workflow = StateGraph(ProcurementState)
workflow.add_node('validate', validate_compliance)
workflow.add_node('permit_check', verify_regulatory_permits)
workflow.add_edge('validate', 'permit_check')
workflow.add_edge('permit_check', END)
workflow.set_entry_point('validate')
graph = workflow.compile()
