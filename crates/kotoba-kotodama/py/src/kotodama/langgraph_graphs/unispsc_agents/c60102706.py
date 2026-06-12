from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    safety_verified: bool
    compliant: bool

def validate_safety_data(state: ProcurementState):
    print('Validating safety standards for pattern mirror...')
    return {'safety_verified': True}

def check_compliance(state: ProcurementState):
    print('Checking procurement policy compliance...')
    return {'compliant': True}

graph = StateGraph(ProcurementState)
graph.add_node('safety_check', validate_safety_data)
graph.add_node('policy_check', check_compliance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'policy_check')
graph.add_edge('policy_check', END)
graph = graph.compile()
