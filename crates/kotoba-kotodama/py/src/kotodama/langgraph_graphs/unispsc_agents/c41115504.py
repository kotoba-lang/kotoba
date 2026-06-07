from typing import TypedDict
from langgraph.graph import StateGraph, END

class SoundAnalyzerState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_status: str

def validate_physics_specs(state: SoundAnalyzerState):
    specs = state.get('spec_data', {})
    required_keys = ['frequency', 'precision']
    passed = all(k in specs for k in required_keys)
    return {'validation_passed': passed, 'compliance_status': 'COMPLIANT' if passed else 'INCOMPLETE'}

workflow = StateGraph(SoundAnalyzerState)
workflow.add_node('validate', validate_physics_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
