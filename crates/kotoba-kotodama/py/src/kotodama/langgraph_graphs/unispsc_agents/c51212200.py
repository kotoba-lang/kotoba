from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    compliance_passed: bool
    vendor_cert_verified: bool

def validate_batch(state: ProcurementState):
    # Simulate regulatory validation logic
    passed = state.get('batch_id') is not None
    return {'compliance_passed': passed}

def verify_vendor(state: ProcurementState):
    return {'vendor_cert_verified': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_batch)
graph.add_node('verify', verify_vendor)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()
