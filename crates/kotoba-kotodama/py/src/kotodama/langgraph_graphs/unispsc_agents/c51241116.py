from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    api_name: str
    purity_check: bool
    temp_log_verified: bool
    compliant: bool

def validate_purity(state: PharmState):
    # Simulate purity verification for API
    return {'purity_check': True}

def verify_cold_chain(state: PharmState):
    # Verify cold chain documentation
    return {'temp_log_verified': True}

def final_check(state: PharmState):
    return {'compliant': state['purity_check'] and state['temp_log_verified']}

graph = StateGraph(PharmState)
graph.add_node('validate', validate_purity)
graph.add_node('cold_chain', verify_cold_chain)
graph.add_node('final', final_check)
graph.add_edge('validate', 'cold_chain')
graph.add_edge('cold_chain', 'final')
graph.add_edge('final', END)
graph.set_entry_point('validate')
graph = graph.compile()
