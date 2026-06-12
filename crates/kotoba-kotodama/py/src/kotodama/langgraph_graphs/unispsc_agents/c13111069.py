from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    material_id: str
    specs: dict
    validation_passed: bool
    inspection_logs: List[str]

def validate_material_specs(state: CarbonFiberState) -> CarbonFiberState:
    specs = state.get('specs', {})
    is_valid = specs.get('tensile_strength_mpa', 0) > 3000 and specs.get('fiber_volume_fraction', 0) > 0.6
    return {'validation_passed': is_valid, 'inspection_logs': ['Specs validated: ' + str(is_valid)]}

def structural_integrity_check(state: CarbonFiberState) -> CarbonFiberState:
    if not state.get('validation_passed'):
        return {'inspection_logs': state['inspection_logs'] + ['Structural check failed due to spec mismatch']}
    return {'inspection_logs': state['inspection_logs'] + ['Structural integrity confirmed']}

graph = StateGraph(CarbonFiberState)
graph.add_node('validate', validate_material_specs)
graph.add_node('structural', structural_integrity_check)
graph.add_edge('validate', 'structural')
graph.add_edge('structural', END)
graph.set_entry_point('validate')
graph = graph.compile()
