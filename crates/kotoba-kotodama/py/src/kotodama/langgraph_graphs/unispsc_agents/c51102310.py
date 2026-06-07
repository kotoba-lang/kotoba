from langgraph.graph import StateGraph, END
from typing import TypedDict

class PharmState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_cleared: bool

def validate_batch(state: PharmState):
    return {'purity_check': True}

def verify_compliance(state: PharmState):
    return {'compliance_cleared': True}

graph = StateGraph(PharmState)
graph.add_node('validate', validate_batch)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
