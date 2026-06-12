from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LightingProcurementState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
    errors: List[str]

def validate_specs(state: LightingProcurementState):
    specs = state.get('spec_sheet', {})
    errors = []
    if specs.get('cri', 0) < 90: errors.append('CRI below professional threshold')
    if not specs.get('ip_rating'): errors.append('Missing IP rating')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

graph = StateGraph(LightingProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
