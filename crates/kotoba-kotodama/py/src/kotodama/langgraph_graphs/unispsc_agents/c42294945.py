from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_check: bool
    sterilization_verified: bool
    compliance_passed: bool

def validate_specs(state: ProcurementState):
    return {'spec_check': True}

def verify_medical_compliance(state: ProcurementState):
    return {'sterilization_verified': True, 'compliance_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', verify_medical_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')

graph = graph.compile()
