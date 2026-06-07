from typing import TypedDict
from langgraph.graph import StateGraph, END

class VFDState(TypedDict):
    spec_data: dict
    validated: bool
    export_control_check: bool

def validate_specs(state: VFDState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['voltage', 'power', 'ip_rating'])
    return {'validated': is_valid}

def check_export_licenses(state: VFDState):
    # Simulate dual-use logic
    return {'export_control_check': True}

graph = StateGraph(VFDState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_licenses)
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph.set_entry_point('validate')
graph = graph.compile()
