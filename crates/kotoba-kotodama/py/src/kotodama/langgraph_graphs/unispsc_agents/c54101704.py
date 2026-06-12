from typing import TypedDict
from langgraph.graph import StateGraph, END

class MandrelState(TypedDict):
    spec_data: dict
    validation_result: bool
    error_log: list

def validate_geometry(state: MandrelState):
    spec = state.get('spec_data', {})
    is_valid = 'taper_accuracy' in spec and 'material' in spec
    return {'validation_result': is_valid, 'error_log': [] if is_valid else ['Missing specs']}

def approval_node(state: MandrelState):
    return {'validation_result': True}

graph = StateGraph(MandrelState)
graph.add_node('validate', validate_geometry)
graph.add_node('approve', approval_node)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
