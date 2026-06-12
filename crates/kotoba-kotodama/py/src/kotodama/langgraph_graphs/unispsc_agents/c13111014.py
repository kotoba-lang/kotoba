from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    spec_data: Dict[str, Any]
    validation_passed: bool
    export_license_status: str
    material_compliance: List[str]

def validate_specs(state: CarbonFiberState) -> CarbonFiberState:
    spec = state.get('spec_data', {})
    # Ensure critical mechanical properties are present
    required = ['tensile_strength_mpa', 'modulus_of_elasticity_gpa']
    state['validation_passed'] = all(k in spec for k in required)
    return state

def check_export_controls(state: CarbonFiberState) -> CarbonFiberState:
    # Dual-use check placeholder
    spec = state.get('spec_data', {})
    if spec.get('tensile_strength_mpa', 0) > 4000:
        state['export_license_status'] = 'REQUIRED'
    else:
        state['export_license_status'] = 'VERIFIED_STANDARD'
    return state

graph = StateGraph(CarbonFiberState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
