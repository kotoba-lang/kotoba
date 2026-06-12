from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalDeviceState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: SurgicalDeviceState):
    specs = state.get('spec_data', {})
    required = ['material_grade', 'iso_cert']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_report': 'Validated' if passed else 'Failed'}

workflow = StateGraph(SurgicalDeviceState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
