from typing import TypedDict
from langgraph.graph import StateGraph, END

class SandBathState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: SandBathState):
    specs = state.get('spec_data', {})
    valid = 'temperature_range_celsius' in specs and 'power_requirements' in specs
    return {'validated': valid, 'error_log': [] if valid else ['Missing technical parameters']}

def approval_node(state: SandBathState):
    return {'validated': True}

graph = StateGraph(SandBathState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
