from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    purity_validated: bool
    temp_log_verified: bool
    compliance_cleared: bool

def validate_purity(state: PharmState) -> PharmState:
    state['purity_validated'] = True
    return state

def verify_logistics(state: PharmState) -> PharmState:
    state['temp_log_verified'] = True
    return state

def check_compliance(state: PharmState) -> PharmState:
    state['compliance_cleared'] = state['purity_validated'] and state['temp_log_verified']
    return state

graph = StateGraph(PharmState)
graph.add_node('validate', validate_purity)
graph.add_node('logistics', verify_logistics)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
