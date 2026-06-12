from typing import TypedDict
from langgraph.graph import StateGraph, END

class EKGSystemState(TypedDict):
    device_id: str
    compliance_check: bool
    validation_passed: bool

def validate_medical_standards(state: EKGSystemState):
    # Simulate regulatory validation
    state['validation_passed'] = True
    return state

def check_security_compliance(state: EKGSystemState):
    # Ensure data protection standards
    state['compliance_check'] = True
    return state

graph = StateGraph(EKGSystemState)
graph.add_node('validate_standards', validate_medical_standards)
graph.add_node('check_security', check_security_compliance)
graph.set_entry_point('validate_standards')
graph.add_edge('validate_standards', 'check_security')
graph.add_edge('check_security', END)
graph = graph.compile()
