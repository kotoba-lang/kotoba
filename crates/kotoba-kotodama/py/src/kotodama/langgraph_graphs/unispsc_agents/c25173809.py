from typing import TypedDict
from langgraph.graph import StateGraph, END

class AxleState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: AxleState):
    specs = state.get('spec_data', {})
    required = ['material_grade', 'load_capacity']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_report': 'Validated' if passed else 'Failed'}

def generate_report(state: AxleState):
    return {'compliance_report': f'Report Generated: {state['validation_passed']}'}

graph = StateGraph(AxleState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
