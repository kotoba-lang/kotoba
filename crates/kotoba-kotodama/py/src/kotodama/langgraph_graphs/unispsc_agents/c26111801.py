from typing import TypedDict
from langgraph.graph import StateGraph, END

class VBeltState(TypedDict):
    belt_specs: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: VBeltState):
    specs = state.get('belt_specs', {})
    required = ['belt_profile', 'effective_length_mm']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'error_log': [] if passed else ['Missing technical specs']}

def route_by_validation(state: VBeltState):
    return 'validate' if not state['validation_passed'] else END

graph = StateGraph(VBeltState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
