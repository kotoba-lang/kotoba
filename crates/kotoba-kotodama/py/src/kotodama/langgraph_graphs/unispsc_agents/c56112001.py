from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    component_type: str
    specs_verified: bool
    compliance_cleared: bool

def validate_specs(state: ProcurementState):
    print('Validating component specifications...')
    return {'specs_verified': True}

def check_compliance(state: ProcurementState):
    print('Checking regulatory compliance...')
    return {'compliance_cleared': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
