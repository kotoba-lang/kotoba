from typing import TypedDict
from langgraph.graph import StateGraph, END

class GearState(TypedDict):
    gear_specs: dict
    validation_passed: bool
    error_logs: str

def validate_specs(state: GearState):
    specs = state.get('gear_specs', {})
    required = ['Material', 'Hardness', 'Tolerance']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'error_logs': 'Pass' if passed else 'Missing fields'}

def route_by_validation(state: GearState):
    return 'process' if state['validation_passed'] else 'END'

graph = StateGraph(GearState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation, {'process': 'process', 'END': END})
graph.add_node('process', lambda state: {'error_logs': 'Processing gear geometry...'})
graph.add_edge('process', END)

graph = graph.compile()
