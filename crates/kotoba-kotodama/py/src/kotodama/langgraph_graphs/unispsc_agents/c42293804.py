from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    part_number: str
    spec_verified: bool
    sterility_check: bool

def validate_specs(state: SurgicalState):
    state['spec_verified'] = state.get('part_number', '').startswith('TUN')
    return state

def check_sterility(state: SurgicalState):
    state['sterility_check'] = True
    return state

graph = StateGraph(SurgicalState)
graph.add_node('validate', validate_specs)
graph.add_node('sterility', check_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()
