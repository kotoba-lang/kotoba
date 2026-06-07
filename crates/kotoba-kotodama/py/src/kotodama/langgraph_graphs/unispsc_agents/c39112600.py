from typing import TypedDict
from langgraph.graph import StateGraph, END

class LightingState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_safety_specs(state: LightingState):
    specs = state.get('spec_data', {})
    compliant = 'safety_certification_standard' in specs and specs['burn_time_duration'] > 0
    return {'is_compliant': compliant}

graph = StateGraph(LightingState)
graph.add_node('validate', validate_safety_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
