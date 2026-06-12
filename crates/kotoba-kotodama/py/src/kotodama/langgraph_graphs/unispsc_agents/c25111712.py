from typing import TypedDict
from langgraph.graph import StateGraph, END

class FrigateProcurementState(TypedDict):
    hull_id: str
    compliance_cleared: bool
    defense_spec_verified: bool

def validate_specs(state: FrigateProcurementState):
    state['defense_spec_verified'] = True
    return state

def run_security_check(state: FrigateProcurementState):
    state['compliance_cleared'] = True
    return state

graph = StateGraph(FrigateProcurementState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('security_check', run_security_check)
graph.add_edge('validate_specs', 'security_check')
graph.add_edge('security_check', END)
graph.set_entry_point('validate_specs')
graph = graph.compile()
