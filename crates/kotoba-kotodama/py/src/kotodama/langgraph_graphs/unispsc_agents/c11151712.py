from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AbrasiveState(TypedDict):
    material_id: str
    quality_metrics: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    status: str

def validate_composition(state: AbrasiveState):
    metrics = state.get('quality_metrics', {})
    if metrics.get('purity_percent', 0) < 99.5:
        return {'validation_logs': ['Low purity detected in composition'], 'status': 'REJECTED'}
    return {'validation_logs': ['Composition validated'], 'status': 'PASS'}

def check_particle_size(state: AbrasiveState):
    if state['status'] == 'REJECTED': return state
    metrics = state.get('quality_metrics', {})
    if not (10 <= metrics.get('mean_microns', 0) <= 50):
        return {'validation_logs': ['Particle size out of spec'], 'status': 'REJECTED'}
    return {'validation_logs': ['Particle size validated'], 'status': 'APPROVED'}

graph = StateGraph(AbrasiveState)
graph.add_node('validate_comp', validate_composition)
graph.add_node('check_size', check_particle_size)
graph.add_edge('validate_comp', 'check_size')
graph.add_edge('check_size', END)
graph.set_entry_point('validate_comp')
graph = graph.compile()
