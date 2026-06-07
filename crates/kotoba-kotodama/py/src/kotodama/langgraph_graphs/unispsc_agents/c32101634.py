from typing import TypedDict
from langgraph.graph import StateGraph, END

class FlipFlopState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
    compliance_report: str

def validate_tech_specs(state: FlipFlopState):
    specs = state.get('spec_sheet', {})
    required = ['Logic Family', 'Operating Voltage Range']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def generate_compliance(state: FlipFlopState):
    if state['validation_passed']:
        return {'compliance_report': 'Technical requirements met for IC procurement.'}
    return {'compliance_report': 'Missing mandatory technical specifications.'}

graph = StateGraph(FlipFlopState)
graph.add_node('validate', validate_tech_specs)
graph.add_node('compliance', generate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
