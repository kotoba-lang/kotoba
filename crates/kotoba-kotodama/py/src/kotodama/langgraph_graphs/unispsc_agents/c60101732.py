from typing import TypedDict
from langgraph.graph import StateGraph, END

class PointingStickState(TypedDict):
    spec_data: dict
    is_validated: bool
    error_log: list

def validate_specs(state: PointingStickState):
    specs = state.get('spec_data', {})
    errors = []
    if not specs.get('extended_length'): errors.append('Missing length')
    return {'is_validated': len(errors) == 0, 'error_log': errors}

def finish_workflow(state: PointingStickState):
    return {'is_validated': True}

graph = StateGraph(PointingStickState)
graph.add_node('validate', validate_specs)
graph.add_node('finish', finish_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finish')
graph.add_edge('finish', END)
graph = graph.compile()
