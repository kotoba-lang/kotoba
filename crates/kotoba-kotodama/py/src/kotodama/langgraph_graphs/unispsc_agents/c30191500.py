from typing import TypedDict
from langgraph.graph import StateGraph, END

class ScaffoldState(TypedDict):
    load_certified: bool
    inspection_passed: bool
    safety_compliant: bool

def validate_load(state: ScaffoldState):
    state['load_certified'] = True
    return state

def check_safety_standards(state: ScaffoldState):
    state['safety_compliant'] = True
    return state

graph = StateGraph(ScaffoldState)
graph.add_node('validate_load', validate_load)
graph.add_node('safety_check', check_safety_standards)
graph.set_entry_point('validate_load')
graph.add_edge('validate_load', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
