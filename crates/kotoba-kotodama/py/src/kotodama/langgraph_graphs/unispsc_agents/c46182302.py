from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SafetyState(TypedDict):
    lanyard_specs: dict
    validation_passed: bool
    compliance_report: str

def validate_certification(state: SafetyState):
    specs = state.get('lanyard_specs', {})
    # Check for mandatory ANSI/OSHA field
    passed = 'compliance' in specs and specs['compliance'] in ['ANSI Z359.13', 'OSHA 1926.502']
    return {'validation_passed': passed}

def generate_report(state: SafetyState):
    report = 'Compliance verified' if state['validation_passed'] else 'Compliance failed: Standard missing'
    return {'compliance_report': report}

graph = StateGraph(SafetyState)
graph.add_node('validate', validate_certification)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
