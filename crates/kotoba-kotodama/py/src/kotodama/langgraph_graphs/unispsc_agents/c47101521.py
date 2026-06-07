from typing import TypedDict
from langgraph.graph import StateGraph, END

class FiltrationState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_specs(state: FiltrationState):
    specs = state.get('spec_data', {})
    # Check for critical filtration parameters
    required = ['membrane_material', 'pore_size_microns']
    is_valid = all(k in specs for k in required)
    return {'validation_result': is_valid}

def route_processing(state: FiltrationState):
    return 'valid' if state['validation_result'] else 'invalid'

graph = StateGraph(FiltrationState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
