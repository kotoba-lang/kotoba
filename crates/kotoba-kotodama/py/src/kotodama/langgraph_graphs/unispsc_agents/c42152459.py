from typing import TypedDict
from langgraph.graph import StateGraph, END

class WorkflowState(TypedDict):
    post_kit_specs: dict
    validation_result: bool
    compliance_report: str

def validate_medical_grade(state: WorkflowState):
    specs = state.get('post_kit_specs', {})
    is_valid = 'ISO 13485' in specs.get('certifications', [])
    return {'validation_result': is_valid}

def generate_compliance_report(state: WorkflowState):
    result = 'Passed' if state['validation_result'] else 'Failed'
    return {'compliance_report': f'Device compliance verification: {result}'}

graph = StateGraph(WorkflowState)
graph.add_node('validate', validate_medical_grade)
graph.add_node('report', generate_compliance_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
