from typing import TypedDict
from langgraph.graph import StateGraph, END

class FlooringState(TypedDict):
    joist_specs: dict
    validation_passed: bool

def validate_structural_integrity(state: FlooringState):
    specs = state.get('joist_specs', {})
    required = ['load_rating', 'material_grade']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def route_by_validation(state: FlooringState):
    return 'process_order' if state['validation_passed'] else 'request_revision'

graph = StateGraph(FlooringState)
graph.add_node('validate', validate_structural_integrity)
graph.add_node('process_order', lambda s: s)
graph.add_node('request_revision', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process_order', END)
graph.add_edge('request_revision', END)
graph = graph.compile()
