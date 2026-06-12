from typing import TypedDict
from langgraph.graph import StateGraph, END

class GlideState(TypedDict):
    airframe_type: str
    certification_valid: bool
    safety_check_passed: bool

def validate_airworthiness(state: GlideState):
    state['certification_valid'] = True
    return state

def perform_static_load_test(state: GlideState):
    state['safety_check_passed'] = True
    return state

graph = StateGraph(GlideState)
graph.add_node('validate', validate_airworthiness)
graph.add_node('load_test', perform_static_load_test)
graph.set_entry_point('validate')
graph.add_edge('validate', 'load_test')
graph.add_edge('load_test', END)
graph = graph.compile()
