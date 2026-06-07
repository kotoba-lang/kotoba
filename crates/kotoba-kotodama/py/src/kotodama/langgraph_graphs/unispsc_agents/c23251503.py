from typing import TypedDict
from langgraph.graph import StateGraph, END

class MachineState(TypedDict):
    spec_data: dict
    is_compliant: bool
    safety_check_passed: bool

def validate_specs(state: MachineState):
    specs = state.get('spec_data', {})
    state['is_compliant'] = all(k in specs for k in ['max_width', 'thickness'])
    print('Validating hardware specifications...')
    return state

def safety_audit(state: MachineState):
    state['safety_check_passed'] = state.get('spec_data', {}).get('safety_standard') == 'ISO-12643'
    print('Performing mechanical safety audit...')
    return state

graph = StateGraph(MachineState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
