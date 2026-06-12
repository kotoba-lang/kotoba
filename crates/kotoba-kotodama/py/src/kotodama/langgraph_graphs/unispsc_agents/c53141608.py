from typing import TypedDict
from langgraph.graph import StateGraph, END

class BodkinState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_tool_specs(state: BodkinState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('tip_shape') != 'blunt':
        errors.append('Invalid tip shape: must be blunt.')
    return {'validated': len(errors) == 0, 'error_log': errors}

graph = StateGraph(BodkinState)
graph.add_node('validate', validate_tool_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
