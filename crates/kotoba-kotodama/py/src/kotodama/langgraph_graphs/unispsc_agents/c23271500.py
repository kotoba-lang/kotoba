from typing import TypedDict
from langgraph.graph import StateGraph, END

class BrazingState(TypedDict):
    spec_data: dict
    validation_passed: bool
    safety_check_result: str

def validate_specs(state: BrazingState):
    specs = state.get('spec_data', {})
    is_valid = 'max_temp' in specs and 'safety_cert' in specs
    return {'validation_passed': is_valid}

def perform_safety_review(state: BrazingState):
    return {'safety_check_result': 'PASS' if state['validation_passed'] else 'FAIL'}

graph = StateGraph(BrazingState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', perform_safety_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
