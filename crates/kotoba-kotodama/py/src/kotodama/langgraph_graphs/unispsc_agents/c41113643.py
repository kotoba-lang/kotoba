from typing import TypedDict
from langgraph.graph import StateGraph, END

class MeterState(TypedDict):
    specs: dict
    validated: bool
    error_log: list

def validate_meter_specs(state: MeterState):
    specs = state.get('specs', {})
    errors = []
    if 'accuracy' not in specs: errors.append('Missing accuracy')
    if 'voltage' not in specs: errors.append('Missing voltage')
    return {'validated': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: MeterState):
    return 'valid' if state.get('validated') else 'invalid'

graph = StateGraph(MeterState)
graph.add_node('validate', validate_meter_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
