from typing import TypedDict
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: BearingState):
    specs = state.get('spec_data', {})
    errors = []
    if 'load_capacity' not in specs: errors.append('Missing load capacity')
    if 'material' not in specs: errors.append('Missing material cert')

    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def process_procurement(state: BearingState):
    print('Processing high-precision bearing order')
    return state

graph = StateGraph(BearingState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
