from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalTubingState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_tubing_specs(state: DentalTubingState):
    specs = state.get('spec_data', {})
    required = ['material_bio', 'pressure_rating']
    valid = all(key in specs for key in required)
    return {'is_compliant': valid, 'validation_log': ['Spec check complete']}

def route_by_compliance(state: DentalTubingState):
    return 'compliant' if state['is_compliant'] else 'manual_review'

graph = StateGraph(DentalTubingState)
graph.add_node('validate', validate_tubing_specs)
graph.add_conditional_edges('validate', route_by_compliance, {'compliant': END, 'manual_review': END})
graph.set_entry_point('validate')
graph = graph.compile()
