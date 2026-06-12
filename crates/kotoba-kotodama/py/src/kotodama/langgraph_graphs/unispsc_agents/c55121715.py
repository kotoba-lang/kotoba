from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class FlagProcurementState(TypedDict):
    specifications: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: FlagProcurementState):
    specs = state.get('specifications', {})
    required = ['material', 'dimensions']
    passed = all(k in specs for k in required)
    return {**state, 'validation_passed': passed}

def generate_report(state: FlagProcurementState):
    status = 'Passed' if state['validation_passed'] else 'Failed'
    return {**state, 'compliance_report': f'Flag validation status: {status}'}

graph = StateGraph(FlagProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph.set_entry_point('validate')
graph = graph.compile()
