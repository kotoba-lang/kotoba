from typing import TypedDict
from langgraph.graph import StateGraph, END

class SafetyState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_safety_specs(state: SafetyState):
    threshold = state.get('spec_data', {}).get('response_time', 100)
    state['is_compliant'] = threshold < 50
    return state

def safety_routing(state: SafetyState):
    return 'validate' if state.get('spec_data') else END

graph = StateGraph(SafetyState)
graph.add_node('validate', validate_safety_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
