from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WalkerState(TypedDict):
    part_specs: dict
    compliance_checked: bool
    approved: bool

def validate_specs(state: WalkerState):
    specs = state.get('part_specs', {})
    is_compliant = 'weight_capacity_kg' in specs and 'iso_11199' in specs
    return {'compliance_checked': is_compliant}

def approval_check(state: WalkerState):
    return {'approved': state['compliance_checked']}

graph = StateGraph(WalkerState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_check)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
