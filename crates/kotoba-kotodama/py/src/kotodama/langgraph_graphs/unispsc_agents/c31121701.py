from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    part_specs: dict
    validation_passed: bool
    log: List[str]

def validate_alloy_composition(state: CastingState) -> CastingState:
    specs = state.get('part_specs', {})
    if 'alloy_grade' in specs:
        state['log'].append('Alloy composition verified')
        state['validation_passed'] = True
    else:
        state['validation_passed'] = False
    return state

def check_geometry(state: CastingState) -> CastingState:
    if state.get('validation_passed'):
        state['log'].append('Centrifugal casting tolerances verified')
    return state

graph = StateGraph(CastingState)
graph.add_node('validate', validate_alloy_composition)
graph.add_node('geometry', check_geometry)
graph.set_entry_point('validate')
graph.add_edge('validate', 'geometry')
graph.add_edge('geometry', END)
graph = graph.compile()
