from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ResuscitationGraphState(TypedDict):
    part_number: str
    specifications: dict
    validation_passed: bool
    compliance_report: str

def validate_medical_spec(state: ResuscitationGraphState):
    # Simulate stringent medical compliance check
    specs = state.get('specifications', {})
    passed = all(k in specs for k in ['biocompatibility', 'pressure_rating'])
    return {'validation_passed': passed, 'compliance_report': 'Success' if passed else 'Failed Spec Validation'}

def generate_procurement_workflow():
    graph = StateGraph(ResuscitationGraphState)
    graph.add_node('validate', validate_medical_spec)
    graph.set_entry_point('validate')
    graph.add_edge('validate', END)
    return graph.compile()

graph = generate_procurement_workflow()
