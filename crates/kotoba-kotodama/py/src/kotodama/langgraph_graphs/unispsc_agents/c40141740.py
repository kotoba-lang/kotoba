from typing import TypedDict
from langgraph.graph import StateGraph, END

class FuelCockState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_spec(state: FuelCockState):
    spec = state.get('spec_data', {})
    required = ['pressure_rating', 'material', 'seal_type']
    passed = all(k in spec for k in required)
    return {'validation_passed': passed}

def safety_check(state: FuelCockState):
    if state.get('validation_passed'):
        return 'approved'
    return 'rejected'

graph = StateGraph(FuelCockState)
graph.add_node('validate', validate_spec)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
