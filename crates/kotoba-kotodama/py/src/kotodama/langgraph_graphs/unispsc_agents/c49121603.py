from typing import TypedDict
from langgraph.graph import StateGraph, END

class CampingCotState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: CampingCotState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('weight_capacity', 0) < 100:
        errors.append('Weight capacity below standard requirement')
    return {'validated': len(errors) == 0, 'error_log': errors}

graph = StateGraph(CampingCotState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
