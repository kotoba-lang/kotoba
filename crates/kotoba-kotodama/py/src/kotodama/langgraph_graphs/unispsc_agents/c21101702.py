from typing import TypedDict
from langgraph.graph import StateGraph, END

class SprayGraphState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: SprayGraphState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('pressure_rating', 0) < 5:
        errors.append('Insufficient pressure rating')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: SprayGraphState):
    return 'validate' if not state['validation_passed'] else END

graph = StateGraph(SprayGraphState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
