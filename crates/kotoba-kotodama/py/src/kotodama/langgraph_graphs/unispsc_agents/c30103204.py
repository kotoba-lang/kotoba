from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_requirements: dict
    validation_passed: bool
    compliance_report: str

def validate_grating_specs(state: ProcurementState):
    specs = state.get('spec_requirements', {})
    required = ['resin_type', 'load_capacity_rating']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_report': 'Verification complete' if passed else 'Missing specs'}

def generate_procurement_workflow():
    graph = StateGraph(ProcurementState)
    graph.add_node('validate', validate_grating_specs)
    graph.set_entry_point('validate')
    graph.add_edge('validate', END)
    return graph.compile()

graph = generate_procurement_workflow()
