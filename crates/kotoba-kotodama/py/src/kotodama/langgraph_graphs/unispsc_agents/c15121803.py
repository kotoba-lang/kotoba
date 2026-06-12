from typing import TypedDict, Annotated, List, Any
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    material_spec: dict
    validation_results: List[str]
    is_compliant: bool

def validate_material(state: ExtrusionState) -> ExtrusionState:
    spec = state.get('material_spec', {})
    results = []
    if spec.get('tensile_strength_mpa', 0) < 50:
        results.append('Fail: Tensile strength too low')
    if spec.get('thermal_deflection_temp_c', 0) < 120:
        results.append('Fail: Thermal resistance insufficient')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def check_dimensions(state: ExtrusionState) -> ExtrusionState:
    if not state.get('is_compliant'):
        return state
    # Simulate CAD geometry validation logic
    return {'validation_results': state['validation_results'] + ['Pass: Dimensions within tolerance']}

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_material)
graph.add_node('check_dim', check_dimensions)
graph.add_edge('validate', 'check_dim')
graph.add_edge('check_dim', END)
graph.set_entry_point('validate')
graph = graph.compile()
