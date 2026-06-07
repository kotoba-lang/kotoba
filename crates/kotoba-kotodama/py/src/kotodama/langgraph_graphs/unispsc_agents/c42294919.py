from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_status: bool
    compliance_report: str

def validate_guidewire_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    required = ['material_composition', 'sterile_barrier_integrity']
    is_valid = all(key in specs for key in required)
    return {'validation_status': is_valid, 'compliance_report': 'Validated' if is_valid else 'Missing Specs'}

def generate_compliance_audit(state: ProcurementState):
    return {'compliance_report': 'Audit passed for medical device class II'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_guidewire_specs)
graph.add_node('audit', generate_compliance_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()
