from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClutchState(TypedDict):
    cable_spec: dict
    validation_passed: bool

def validate_spec(state: ClutchState):
    spec = state.get('cable_spec', {})
    is_valid = all(k in spec for k in ['tensile', 'length'])
    return {'validation_passed': is_valid}

def process_procurement(state: ClutchState):
    return {'validation_passed': True}

graph = StateGraph(ClutchState)
graph.add_node('validate', validate_spec)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
