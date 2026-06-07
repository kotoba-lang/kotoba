from typing import TypedDict
from langgraph.graph import StateGraph, END

class CamshaftPlugState(TypedDict):
    spec_data: dict
    is_validated: bool
    error_log: list

def validate_specs(state: CamshaftPlugState):
    specs = state.get('spec_data', {})
    critical_fields = ['material', 'outer_diameter', 'pressure_rating']
    errors = [field for field in critical_fields if field not in specs]
    return {'is_validated': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: CamshaftPlugState):
    return 'validate' if not state.get('is_validated') else END

graph = StateGraph(CamshaftPlugState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
