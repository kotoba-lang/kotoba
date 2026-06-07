from typing import TypedDict
from langgraph.graph import StateGraph, END

class OringState(TypedDict):
    material: str
    dimensions: dict
    approved: bool

def validate_specs(state: OringState):
    # Simulate CAD dimension validation logic
    specs = state.get('dimensions', {})
    is_valid = specs.get('id', 0) > 0 and specs.get('cs', 0) > 0
    return {'approved': is_valid}

def update_status(state: OringState):
    print(f'Validation complete: {state.get('approved')}')
    return state

graph = StateGraph(OringState)
graph.add_node('validate', validate_specs)
graph.add_node('status', update_status)
graph.set_entry_point('validate')
graph.add_edge('validate', 'status')
graph.add_edge('status', END)
graph = graph.compile()
