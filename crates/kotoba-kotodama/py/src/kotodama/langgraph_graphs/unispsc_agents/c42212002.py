from typing import TypedDict
from langgraph.graph import StateGraph, END

class KeyTurnerState(TypedDict):
    spec_compliance: bool
    materials_checked: bool
    ergonomic_validation: bool

def validate_specs(state: KeyTurnerState):
    state['spec_compliance'] = True
    return state

def check_ergonomics(state: KeyTurnerState):
    state['ergonomic_validation'] = True
    return state

graph = StateGraph(KeyTurnerState)
graph.add_node('validate', validate_specs)
graph.add_node('ergonomics', check_ergonomics)
graph.add_edge('validate', 'ergonomics')
graph.add_edge('ergonomics', END)
graph.set_entry_point('validate')
graph = graph.compile()
