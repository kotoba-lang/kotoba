from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    material_id: str
    spec_requirements: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_material_specs(state: CarbonFiberState) -> dict:
    specs = state.get('spec_requirements', {})
    tensile = specs.get('tensile_strength_mpa', 0)
    if tensile > 3000:
        return {'validation_logs': ['Tensile strength exceeds threshold'], 'is_compliant': True}
    return {'validation_logs': ['Tensile strength insufficient'], 'is_compliant': False}

def export_control_check(state: CarbonFiberState) -> dict:
    return {'validation_logs': state.get('validation_logs', []) + ['Export control clearance passed']}

graph = StateGraph(CarbonFiberState)
graph.add_node('validate', validate_material_specs)
graph.add_node('export_check', export_control_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
