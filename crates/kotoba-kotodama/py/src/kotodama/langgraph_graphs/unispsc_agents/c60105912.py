from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    content_metadata: dict
    validation_passed: bool
    compliance_report: str

def validate_material_content(state: ProcurementState):
    # Simulate content validation logic for educational safety materials
    metadata = state.get('content_metadata', {})
    state['validation_passed'] = metadata.get('is_evidence_based', False)
    return state

def generate_compliance_brief(state: ProcurementState):
    state['compliance_report'] = 'Material verified against standard child protection guidelines.'
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material_content)
graph.add_node('compliance', generate_compliance_brief)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
