from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    compliance_validated: bool
    sterility_check: bool

def validate_certification(state: ProcurementState):
    # Simulate regulatory validation
    return {'compliance_validated': True}

def verify_sterility(state: ProcurementState):
    # Simulate sterility document verification
    return {'sterility_check': True}

graph = StateGraph(ProcurementState)
graph.add_node('cert_check', validate_certification)
graph.add_node('sterile_check', verify_sterility)
graph.set_entry_point('cert_check')
graph.add_edge('cert_check', 'sterile_check')
graph.add_edge('sterile_check', END)
graph = graph.compile()
