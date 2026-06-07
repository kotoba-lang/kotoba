from typing import TypedDict
from langgraph.graph import StateGraph, END

class RadiometerState(TypedDict):
    spec_data: dict
    validation_status: bool
    error_log: list

def validate_specs(state: RadiometerState):
    specs = state.get('spec_data', {})
    errors = []
    if 'spectral_range_nm' not in specs: errors.append('Missing spectral range')
    return {'validation_status': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: RadiometerState):
    return 'valid' if state['validation_status'] else 'invalid'

graph = StateGraph(RadiometerState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
