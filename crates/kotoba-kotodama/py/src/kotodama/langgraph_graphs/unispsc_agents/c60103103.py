from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GeoboardState(TypedDict):
    spec_completed: bool
    safety_check: bool
    validation_errors: List[str]

def validate_specs(state: GeoboardState):
    errors = []
    if not state.get('material_composition'):
        errors.append('Missing material specs')
    return {'validation_errors': errors, 'spec_completed': len(errors) == 0}

def perform_safety_check(state: GeoboardState):
    return {'safety_check': True}

graph = StateGraph(GeoboardState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', perform_safety_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
