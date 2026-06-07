from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    part_specs: dict
    validation_passed: bool

def validate_titanium_specs(state: State):
    specs = state.get('part_specs', {})
    critical_fields = ['Material Grade', 'Yield Strength']
    passed = all(field in specs for field in critical_fields)
    return {'validation_passed': passed}

def route_verification(state: State):
    return 'validate' if state['validation_passed'] else END

graph = StateGraph(State)
graph.add_node('validate', validate_titanium_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
