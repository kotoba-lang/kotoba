from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    quantity: int
    license_validated: bool
    compliance_cleared: bool

def validate_license(state: ProcurementState):
    state['license_validated'] = True
    return state

def check_compliance(state: ProcurementState):
    state['compliance_cleared'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_license', validate_license)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_license')
graph.add_edge('validate_license', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()
