from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalProcurementState(TypedDict):
    product_id: str
    compliance_verified: bool
    sterility_status: str
    approval_needed: bool

def validate_compliance(state: DentalProcurementState):
    state['compliance_verified'] = True
    state['approval_needed'] = True
    return state

def check_sterility(state: DentalProcurementState):
    state['sterility_status'] = 'Certified'
    return state

graph = StateGraph(DentalProcurementState)
graph.add_node('ValidateCompliance', validate_compliance)
graph.add_node('CheckSterility', check_sterility)
graph.set_entry_point('ValidateCompliance')
graph.add_edge('ValidateCompliance', 'CheckSterility')
graph.add_edge('CheckSterility', END)
graph = graph.compile()
