from typing import TypedDict
from langgraph.graph import StateGraph, END

class RadiatorState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: RadiatorState):
    specs = state.get('spec_data', {})
    errors = []
    if 'heat_transfer_capacity_kW' not in specs: errors.append('Missing thermal rating')
    if 'operating_pressure_rating' not in specs: errors.append('Missing pressure rating')
    return {'validated': len(errors) == 0, 'error_log': errors}

graph = StateGraph(RadiatorState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
