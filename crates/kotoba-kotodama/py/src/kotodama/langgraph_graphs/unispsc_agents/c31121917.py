from typing import TypedDict
from langgraph.graph import StateGraph, END

class MoldState(TypedDict):
    material_specs: dict
    validation_score: float
    approved: bool

def validate_material(state: MoldState):
    # Simulated validation logic for high-spec composite graphite
    spec = state.get('material_specs', {})
    state['validation_score'] = 1.0 if spec.get('temp_rating', 0) > 2000 else 0.0
    return state

def approve_mold(state: MoldState):
    state['approved'] = state['validation_score'] >= 1.0
    return state

graph = StateGraph(MoldState)
graph.add_node('validate', validate_material)
graph.add_node('approve', approve_mold)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
