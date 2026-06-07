from typing import TypedDict
from langgraph.graph import StateGraph, END

class OphthalmoState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: OphthalmoState):
    specs = state.get('spec_data', {})
    errors = []
    if 'ISO 13485' not in specs.get('certifications', []):
        errors.append('Missing mandatory Medical ISO certification')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

graph = StateGraph(OphthalmoState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
