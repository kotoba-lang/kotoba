from typing import TypedDict
from langgraph.graph import StateGraph, END

class TractionState(TypedDict):
    device_id: str
    compliance_checked: bool
    sterility_verified: bool
    is_approved: bool

def validate_materials(state: TractionState):
    # Simulate material compliance check for surgical hardware
    state['compliance_checked'] = True
    return state

def verify_sterility(state: TractionState):
    # Simulate sterilization documentation check
    state['sterility_verified'] = True
    state['is_approved'] = state['compliance_checked'] and state['sterility_verified']
    return state

graph = StateGraph(TractionState)
graph.add_node('validate', validate_materials)
graph.add_node('sterility', verify_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()
