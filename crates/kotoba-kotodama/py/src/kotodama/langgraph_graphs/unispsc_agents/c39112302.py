from typing import TypedDict
from langgraph.graph import StateGraph, END

class FilterState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: FilterState):
    specs = state.get('spec_data', {})
    errors = []
    if 'fwhm_bandwidth' not in specs: errors.append('Missing FWHM data')
    if 'optical_density' not in specs: errors.append('Missing OD rating')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: FilterState):
    return 'process' if state['validation_passed'] else 'fail'

graph = StateGraph(FilterState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda s: s)
graph.add_node('fail', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph.add_edge('fail', END)
graph = graph.compile()
