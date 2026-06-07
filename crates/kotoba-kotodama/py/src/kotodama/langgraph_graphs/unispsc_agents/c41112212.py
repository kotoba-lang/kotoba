from typing import TypedDict
from langgraph.graph import StateGraph, END

class ThermoState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_specs(state: ThermoState):
    specs = state.get('spec_data', {})
    required = ['accuracy_tolerance', 'measurement_range_celsius']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def approval_node(state: ThermoState):
    return {'validation_passed': True}

graph = StateGraph(ThermoState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_node)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
