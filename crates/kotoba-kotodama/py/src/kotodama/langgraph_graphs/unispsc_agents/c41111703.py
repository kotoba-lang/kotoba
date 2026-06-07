from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicroscopeState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_optics(state: MicroscopeState):
    specs = state.get('spec_data', {})
    magnification = specs.get('magnification', 0)
    is_valid = magnification > 0
    return {'validation_passed': is_valid, 'error_log': [] if is_valid else ['Invalid magnification']}

def route_verification(state: MicroscopeState):
    return 'end' if state['validation_passed'] else 'end'

graph = StateGraph(MicroscopeState)
graph.add_node('validate', validate_optics)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
