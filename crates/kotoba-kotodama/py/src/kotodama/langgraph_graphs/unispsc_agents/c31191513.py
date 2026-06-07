from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GlassBeadState(TypedDict):
    bead_specs: dict
    validation_passed: bool
    errors: List[str]

def validate_bead_quality(state: GlassBeadState):
    specs = state.get('bead_specs', {})
    errors = []
    if specs.get('roundness', 0) < 80:
        errors.append('Roundness below standard')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

def process_procurement(state: GlassBeadState):
    return {'status': 'processed' if state['validation_passed'] else 'rejected'}

graph = StateGraph(GlassBeadState)
graph.add_node('validate', validate_bead_quality)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
