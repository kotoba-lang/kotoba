from typing import TypedDict
from langgraph.graph import StateGraph, END

class GeoMirrorState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: GeoMirrorState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('angular_accuracy_degrees', 0) > 0.5:
        errors.append('Angular accuracy outside acceptable threshold.')
    return {'validated': len(errors) == 0, 'error_log': errors}

workflow = StateGraph(GeoMirrorState)
workflow.add_node('validation', validate_specs)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
