from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrecisionState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: PrecisionState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('accuracy', 0) > 0.01:
        errors.append('Precision exceeds allowable tolerance')
    return {'validated': len(errors) == 0, 'error_log': errors}

def approval_step(state: PrecisionState):
    return {'validated': True}

graph = StateGraph(PrecisionState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
