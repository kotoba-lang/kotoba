from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ClipState(TypedDict):
    spec_data: dict
    validation_passed: bool
    errors: List[str]

def validate_dimensions(state: ClipState):
    specs = state.get('spec_data', {})
    errors = []
    if 'tolerance' not in specs: errors.append('Missing tolerance data')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

def check_material_standard(state: ClipState):
    return {'validation_passed': state.get('spec_data', {}).get('material_grade') is not None}

graph = StateGraph(ClipState)
graph.add_node('validate', validate_dimensions)
graph.add_node('standards', check_material_standard)
graph.set_entry_point('validate')
graph.add_edge('validate', 'standards')
graph.add_edge('standards', END)
graph = graph.compile()
