from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurfaceProcurementState(TypedDict):
    spec_details: dict
    validation_checks: list
    approval_status: bool

def validate_surface_specs(state: SurfaceProcurementState):
    specs = state.get('spec_details', {})
    checks = [k for k in ['material_composition', 'surface_hardness_rating'] if k in specs]
    return {'validation_checks': checks, 'approval_status': len(checks) >= 2}

graph = StateGraph(SurfaceProcurementState)
graph.add_node('validate', validate_surface_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
