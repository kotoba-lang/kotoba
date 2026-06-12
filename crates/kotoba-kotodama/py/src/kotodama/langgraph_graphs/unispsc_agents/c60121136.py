from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CellophaneState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_approved: bool

def validate_film_specs(state: CellophaneState) -> CellophaneState:
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('thickness', 0) < 10: errors.append('Thickness below threshold.')
    if not specs.get('food_grade', False): errors.append('Food safety cert missing.')
    return {**state, 'validation_errors': errors, 'is_approved': len(errors) == 0}

def route_by_approval(state: CellophaneState) -> str:
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(CellophaneState)
graph.add_node('validator', validate_film_specs)
graph.set_entry_point('validator')
graph.add_conditional_edges('validator', route_by_approval, {'approved': END, 'rejected': END})
graph = graph.compile()
