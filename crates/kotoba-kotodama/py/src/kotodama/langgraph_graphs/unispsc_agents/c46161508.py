from typing import TypedDict
from langgraph.graph import StateGraph, END
class TrafficSafetyState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_report: str
def validate_specs(state: TrafficSafetyState):
    specs = state.get('spec_data', {})
    required = ['reflective_material_grade', 'base_weight_kg']
    is_valid = all(key in specs for key in required)
    return {'is_compliant': is_valid, 'validation_report': 'Success' if is_valid else 'Missing specs'}
def finalize_procurement(state: TrafficSafetyState):
    return {'validation_report': 'Procurement documentation generated'}
graph = StateGraph(TrafficSafetyState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
