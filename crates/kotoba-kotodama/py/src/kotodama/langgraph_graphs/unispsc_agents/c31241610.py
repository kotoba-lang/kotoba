from typing import TypedDict
from langgraph.graph import StateGraph, END

class OpticalMaterialState(TypedDict):
    material_type: str
    transmission_data: dict
    compliance_check: bool

def validate_specs(state: OpticalMaterialState):
    # Simulate CAD/Spec validation for IR blanks
    state['compliance_check'] = 'purity' in state and state['purity'] > 99.9
    return state

def check_export_controls(state: OpticalMaterialState):
    # Dual-use regulatory check
    state['compliance_check'] = state.get('compliance_check', False) and True
    return state

graph = StateGraph(OpticalMaterialState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
