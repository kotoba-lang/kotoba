from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShelterState(TypedDict):
    material_specs: dict
    compliance_checked: bool
    approved: bool

def validate_structural_specs(state: ShelterState):
    # Simulate CAD/Engineering verification
    specs = state.get('material_specs', {})
    state['compliance_checked'] = 'fire_rating' in specs and 'load_capacity' in specs
    return state

def review_procurement(state: ShelterState):
    state['approved'] = state.get('compliance_checked', False)
    return state

graph = StateGraph(ShelterState)
graph.add_node('validate', validate_structural_specs)
graph.add_node('review', review_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'review')
graph.add_edge('review', END)
graph = graph.compile()
