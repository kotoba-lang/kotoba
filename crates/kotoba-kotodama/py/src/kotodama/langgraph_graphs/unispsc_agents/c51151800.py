from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_verified: bool

def validate_purity(state: PharmState):
    return {'purity_check': True}

def verify_compliance(state: PharmState):
    return {'compliance_verified': True}

graph = StateGraph(PharmState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_compliance')
graph.add_edge('verify_compliance', END)
graph = graph.compile()
