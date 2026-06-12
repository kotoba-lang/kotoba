from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SealingFilmState(TypedDict):
    material: str
    width_mm: float
    length_m: float
    is_sterile: bool
    validation_errors: List[str]

def validate_specs(state: SealingFilmState):
    errors = []
    if not state.get('material'):
        errors.append('Material specification missing')
    if state.get('width_mm', 0) <= 0:
        errors.append('Invalid width')
    return {'validation_errors': errors}

def approval_check(state: SealingFilmState):
    return 'approved' if not state['validation_errors'] else 'rejected'

graph = StateGraph(SealingFilmState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
