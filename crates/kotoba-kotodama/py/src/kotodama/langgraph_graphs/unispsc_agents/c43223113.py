from typing import TypedDict
from langgraph.graph import StateGraph, END

class AntennaState(TypedDict):
    specs: dict
    approved: bool
    error_log: list

def validate_specs(state: AntennaState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('vswr', 1.5) > 2.0:
        errors.append('VSWR exceeds threshold')
    return {'approved': len(errors) == 0, 'error_log': errors}

graph = StateGraph(AntennaState)
graph.add_node('validation', validate_specs)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
