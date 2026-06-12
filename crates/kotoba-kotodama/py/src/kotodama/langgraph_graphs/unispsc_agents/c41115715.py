import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class InjectionState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_medical_spec(state: InjectionState):
    specs = state.get('spec_data', {})
    # Logic to verify flow rate and sterilization certification
    passed = 'FDA_CE_Cert' in specs and specs.get('flow_rate_std', 0) < 0.05
    return {'validation_passed': passed}

def process_compliance(state: InjectionState):
    report = 'Compliance verified' if state['validation_passed'] else 'Compliance failure'
    return {'compliance_report': report}

graph = StateGraph(InjectionState)
graph.add_node('validate', validate_medical_spec)
graph.add_node('compliance', process_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
