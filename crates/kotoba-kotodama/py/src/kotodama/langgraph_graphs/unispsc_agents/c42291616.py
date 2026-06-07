from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    device_id: str
    spec_check: bool
    sterility_verified: bool

def validate_materials(state: State):
    # Simulate material composition validation for medical compliance
    state['spec_check'] = True
    return state

def check_sterility(state: State):
    # Verify sterilization logs for surgical instruments
    state['sterility_verified'] = True
    return state

graph = StateGraph(State)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_sterility', check_sterility)
graph.add_edge('validate_materials', 'check_sterility')
graph.add_edge('check_sterility', END)
graph.set_entry_point('validate_materials')
graph = graph.compile()
