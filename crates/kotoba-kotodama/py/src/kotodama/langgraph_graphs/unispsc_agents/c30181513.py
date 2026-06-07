from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_dimensions(state: ProcurementState):
    specs = state.get('spec_data', {})
    is_valid = 'mounting_hole_mm' in specs and 'width_mm' in specs
    return {'validation_passed': is_valid}

def check_compliance(state: ProcurementState):
    return {'compliance_report': 'Safety and hygienic compliance verified.' if state['validation_passed'] else 'Compliance failed'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_dimensions)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
