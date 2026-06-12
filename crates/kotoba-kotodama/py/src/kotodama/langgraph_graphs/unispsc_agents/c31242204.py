from typing import TypedDict
from langgraph.graph import StateGraph, END

class OpticalSpecState(TypedDict):
    specs: dict
    validated: bool
    error_log: list

def validate_optical_data(state: OpticalSpecState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('transmittance', 0) < 0.85:
        errors.append('Insufficient transmittance')
    return {'validated': len(errors) == 0, 'error_log': errors}

def process_workflow(state: OpticalSpecState):
    print('Processing optical diffuser procurement specs...')
    return state

graph = StateGraph(OpticalSpecState)
graph.add_node('validate', validate_optical_data)
graph.add_node('process', process_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
