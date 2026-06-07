from typing import TypedDict
from langgraph.graph import StateGraph, END

class AidState(TypedDict):
    needs_customization: bool
    safety_check_passed: bool
    spec_compliance: bool

def validate_specs(state: AidState):
    state['spec_compliance'] = True
    return state

def perform_safety_check(state: AidState):
    state['safety_check_passed'] = True
    return state

graph = StateGraph(AidState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', perform_safety_check)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')

graph = graph.compile()
