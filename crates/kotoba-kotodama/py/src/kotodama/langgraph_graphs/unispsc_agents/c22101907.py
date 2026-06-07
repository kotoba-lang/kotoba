from typing import TypedDict
from langgraph.graph import StateGraph, END

class FastenerState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_bolt_specs(state: FastenerState):
    specs = state.get('spec_data', {})
    required = ['grade', 'diameter', 'material']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_report': 'Validated' if passed else 'Missing fields'}

def generate_compliance_cert(state: FastenerState):
    if not state['validation_passed']:
        return {'compliance_report': 'Failed qualification'}
    return {'compliance_report': 'Certification Ready'}

graph = StateGraph(FastenerState)
graph.add_node('validate', validate_bolt_specs)
graph.add_node('certify', generate_compliance_cert)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()
