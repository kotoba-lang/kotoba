from langgraph.graph import StateGraph, END
from typing import TypedDict

class LockoutState(TypedDict):
    valve_spec: dict
    compliance_check: bool
    approved: bool

def validate_valve_specs(state: LockoutState):
    # Logic to ensure the lockout device matches valve diameter and pressure requirements
    specs = state.get('valve_spec', {})
    is_valid = 'size' in specs and 'material' in specs
    return {'compliance_check': is_valid}

def approve_procurement(state: LockoutState):
    return {'approved': state['compliance_check']}

graph = StateGraph(LockoutState)
graph.add_node('validate', validate_valve_specs)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
