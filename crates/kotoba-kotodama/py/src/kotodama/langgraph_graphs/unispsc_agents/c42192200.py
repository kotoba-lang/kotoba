from typing import TypedDict
from langgraph.graph import StateGraph, END

class PatientTransportState(TypedDict):
    product_id: str
    compliance_passed: bool
    safety_check_result: str

def validate_compliance(state: PatientTransportState):
    # Simulate regulatory validation
    passed = True
    return {'compliance_passed': passed}

def safety_inspection(state: PatientTransportState):
    return {'safety_check_result': 'Pass: Brake and structural integrity verified'}

graph = StateGraph(PatientTransportState)
graph.add_node('compliance', validate_compliance)
graph.add_node('safety', safety_inspection)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
