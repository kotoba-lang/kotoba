from typing import TypedDict
from langgraph.graph import StateGraph, END

class SwitchState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_switch_specs(state: SwitchState):
    specs = state.get('spec_data', {})
    required = ['voltage', 'ip_rating', 'actuator']
    valid = all(key in specs for key in required)
    return {'is_compliant': valid}

def route_processing(state: SwitchState):
    return 'process' if state['is_compliant'] else END

state_graph = StateGraph(SwitchState)
state_graph.add_node('validate', validate_switch_specs)
state_graph.set_entry_point('validate')
state_graph.add_edge('validate', END)
graph = state_graph.compile()
