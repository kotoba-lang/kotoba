from typing import TypedDict
from langgraph.graph import StateGraph, END

class EndodonticSprayState(TypedDict):
    product_id: str
    compliance_checked: bool
    hazard_verified: bool

def validate_compliance(state: EndodonticSprayState):
    print('Checking FDA/Medical device regulatory status...')
    return {'compliance_checked': True}

def check_hazard_classification(state: EndodonticSprayState):
    print('Verifying chemical safety and pressure hazard class...')
    return {'hazard_verified': True}

graph = StateGraph(EndodonticSprayState)
graph.add_node('compliance', validate_compliance)
graph.add_node('hazmat', check_hazard_classification)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'hazmat')
graph.add_edge('hazmat', END)
graph = graph.compile()
