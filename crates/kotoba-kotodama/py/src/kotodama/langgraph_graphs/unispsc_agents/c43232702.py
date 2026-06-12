from typing import TypedDict
from langgraph.graph import StateGraph, END

class SoftwareState(TypedDict):
    software_name: str
    security_verified: bool
    compliance_checked: bool

def validate_security(state: SoftwareState):
    return {'security_verified': True}

def verify_compliance(state: SoftwareState):
    return {'compliance_checked': True}

graph = StateGraph(SoftwareState)
graph.add_node('security', validate_security)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('security')
graph.add_edge('security', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
