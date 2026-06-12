from typing import TypedDict
from langgraph.graph import StateGraph, END

class XrayState(TypedDict):
    product_code: str
    compliance_verified: bool
    radiation_safety_check: bool

def validate_compliance(state: XrayState):
    print('Checking regulatory certifications...')
    return {'compliance_verified': True}

def safety_audit(state: XrayState):
    print('Performing radiation shielding safety protocols...')
    return {'radiation_safety_check': True}

graph = StateGraph(XrayState)
graph.add_node('verify_certs', validate_compliance)
graph.add_node('safety_check', safety_audit)
graph.set_entry_point('verify_certs')
graph.add_edge('verify_certs', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
