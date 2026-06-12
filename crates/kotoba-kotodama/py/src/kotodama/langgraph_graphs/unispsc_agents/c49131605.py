from typing import TypedDict
from langgraph.graph import StateGraph, END

class RifleProcurementState(TypedDict):
    license_validated: bool
    compliance_passed: bool
    specs_verified: bool

def validate_license(state):
    print('Verifying end-user license...')
    return {'license_validated': True}

def check_compliance(state):
    print('Checking export/import compliance...')
    return {'compliance_passed': True}

def verify_specs(state):
    print('Validating rifle technical specs...')
    return {'specs_verified': True}

graph = StateGraph(RifleProcurementState)
graph.add_node('validate', validate_license)
graph.add_node('compliance', check_compliance)
graph.add_node('specs', verify_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', 'specs')
graph.add_edge('specs', END)
graph = graph.compile()
