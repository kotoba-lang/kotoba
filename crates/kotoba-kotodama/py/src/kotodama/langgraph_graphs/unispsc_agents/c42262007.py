from typing import TypedDict
from langgraph.graph import StateGraph, END

class EmbalmingNeedleState(TypedDict):
    spec_requirements: dict
    validation_passed: bool

def validate_needle_specs(state: EmbalmingNeedleState):
    specs = state.get('spec_requirements', {})
    is_valid = all(k in specs for k in ['gauge', 'material'])
    return {'validation_passed': is_valid}

graph = StateGraph(EmbalmingNeedleState)
graph.add_node('validate', validate_needle_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
