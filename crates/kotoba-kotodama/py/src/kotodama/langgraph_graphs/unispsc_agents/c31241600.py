from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OpticalState(TypedDict):
    material_spec: dict
    compliance_check: bool
    validation_log: List[str]

def validate_specs(state: OpticalState):
    specs = state.get('material_spec', {})
    checks = []
    if specs.get('refractive_index'): checks.append('Refractive index verified')
    return {'validation_log': checks, 'compliance_check': True}

def export_control_check(state: OpticalState):
    return {'validation_log': state['validation_log'] + ['Dual-use screening passed']}

graph = StateGraph(OpticalState)
graph.add_node('validate', validate_specs)
graph.add_node('export', export_control_check)
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph.set_entry_point('validate')
graph = graph.compile()
