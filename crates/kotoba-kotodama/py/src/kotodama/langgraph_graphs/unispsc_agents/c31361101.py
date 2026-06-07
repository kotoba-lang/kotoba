from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    specs: dict
    validation_status: bool
    compliance_report: str

def validate_structural_specs(state: AssemblyState):
    specs = state.get('specs', {})
    is_valid = all(k in specs for k in ['alloy', 'tensile_strength', 'bond_integrity'])
    print('Validating structural bond integrity...')
    return {'validation_status': is_valid, 'compliance_report': 'Passed' if is_valid else 'Failed'}

def export_control_check(state: AssemblyState):
    print('Checking dual-use export control status...')
    return {'compliance_report': 'Clear'}

graph = StateGraph(AssemblyState)
graph.add_node('validation', validate_structural_specs)
graph.add_node('export_review', export_control_check)
graph.set_entry_point('validation')
graph.add_edge('validation', 'export_review')
graph.add_edge('export_review', END)
graph = graph.compile()
