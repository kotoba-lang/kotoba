from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_chemistry(state: State):
    # Simulate regulatory validation for leveling agents
    specs = state.get('spec_data', {})
    compliant = 'flash_point' in specs and 'chemical_composition' in specs
    return {'is_compliant': compliant}

def routing(state: State):
    return 'validate' if state.get('spec_data') else END

graph = StateGraph(State)
graph.add_node('validate', validate_chemistry)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
