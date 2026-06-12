from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_code: str
    license_valid: bool
    compliance_cleared: bool
    approval_status: str

def verify_license(state: ProcurementState):
    # Simulate regulatory lookup
    state['license_valid'] = True
    return {'license_valid': True}

def check_compliance(state: ProcurementState):
    # Simulate audit for controlled substances
    state['compliance_cleared'] = True
    return {'compliance_cleared': True}

graph = StateGraph(ProcurementState)
graph.add_node('verify_license', verify_license)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('verify_license')
graph.add_edge('verify_license', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()
