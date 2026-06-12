from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_dimensions(state: ExtrusionState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['gauge', 'material', 'tolerance'])
    return {'validation_passed': is_valid, 'error_log': [] if is_valid else ['Missing req specs']}

def route_by_validation(state: ExtrusionState):
    return 'process' if state['validation_passed'] else 'reject'

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_dimensions)
graph.add_node('process', lambda x: x)
graph.add_node('reject', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph.add_edge('reject', END)
graph = graph.compile()
