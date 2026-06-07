from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AlloyState(TypedDict):
    batch_id: str
    purity_check: bool
    particle_distribution: float
    status: str

def validate_composition(state: AlloyState) -> AlloyState:
    # Logic to verify alloy composition meets aerospace standards
    state['purity_check'] = state.get('purity_check', False)
    state['status'] = 'COMPOSITION_VALIDATED' if state['purity_check'] else 'COMPOSITION_FAILED'
    return state

def analyze_particles(state: AlloyState) -> AlloyState:
    # Logic for particle size distribution analysis
    if state['status'] == 'COMPOSITION_VALIDATED':
        state['status'] = 'PARTICLES_ANALYZED'
    return state

graph = StateGraph(AlloyState)
graph.add_node('validate', validate_composition)
graph.add_node('analyze', analyze_particles)
graph.add_edge('validate', 'analyze')
graph.add_edge('analyze', END)
graph.set_entry_point('validate')
graph = graph.compile()
