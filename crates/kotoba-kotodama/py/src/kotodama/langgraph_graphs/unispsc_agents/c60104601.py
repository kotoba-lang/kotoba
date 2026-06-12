from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForceTableState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_physics_specs(state: ForceTableState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('graduation_accuracy', 0) > 0.5:
        errors.append('Accuracy tolerance exceeds limits')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: ForceTableState):
    return 'validate' if state.get('validation_passed') else END

graph = StateGraph(ForceTableState)
graph.add_node('validate', validate_physics_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
