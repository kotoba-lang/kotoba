from typing import TypedDict
from langgraph.graph import StateGraph, END

class GuidewireState(TypedDict):
    part_number: str
    compliance_verified: bool
    sterility_check: bool

def validate_compliance(state: GuidewireState):
    state['compliance_verified'] = True
    return state

def check_sterility(state: GuidewireState):
    state['sterility_check'] = True
    return state

graph = StateGraph(GuidewireState)
graph.add_node('validate', validate_compliance)
graph.add_node('sterility', check_sterility)
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph.set_entry_point('validate')
graph = graph.compile()
