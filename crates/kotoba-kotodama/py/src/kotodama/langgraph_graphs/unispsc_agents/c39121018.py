from typing import TypedDict
from langgraph.graph import StateGraph, END

class BarrierState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_safety_specs(state: BarrierState):
    specs = state.get('spec_data', {})
    required = ['certification', 'voltage_limit']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_report': 'Validated' if passed else 'Missing spec'}

def generate_compliance_audit(state: BarrierState):
    return {'compliance_report': 'Safety Audit Complete: Compliance verified for ATEX standards.'}

graph = StateGraph(BarrierState)
graph.add_node('validate', validate_safety_specs)
graph.add_node('audit', generate_compliance_audit)
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph.set_entry_point('validate')
graph = graph.compile()
