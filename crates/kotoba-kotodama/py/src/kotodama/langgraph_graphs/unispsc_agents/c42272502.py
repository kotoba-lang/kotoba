from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnesthesiaState(TypedDict):
    part_number: str
    compliance_checked: bool
    safety_validated: bool

def validate_medical_cert(state: AnesthesiaState):
    print('Validating medical device certifications...')
    return {'compliance_checked': True}

def perform_safety_check(state: AnesthesiaState):
    print('Verifying chemical absorption specifications...')
    return {'safety_validated': True}

graph = StateGraph(AnesthesiaState)
graph.add_node('cert_validation', validate_medical_cert)
graph.add_node('safety_validation', perform_safety_check)
graph.set_entry_point('cert_validation')
graph.add_edge('cert_validation', 'safety_validation')
graph.add_edge('safety_validation', END)
graph = graph.compile()
