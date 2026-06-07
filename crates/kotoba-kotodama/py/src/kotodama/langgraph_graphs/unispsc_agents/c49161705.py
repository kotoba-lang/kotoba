from typing import TypedDict
from langgraph.graph import StateGraph, END

class PoleState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_pole_specs(state: PoleState):
    # Simulate validation logic for vaulting poles
    specs = state.get('spec_data', {})
    weight_rating = specs.get('weight_rating', 0)
    state['is_compliant'] = weight_rating > 40
    return state

graph = StateGraph(PoleState)
graph.add_node('validate', validate_pole_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
