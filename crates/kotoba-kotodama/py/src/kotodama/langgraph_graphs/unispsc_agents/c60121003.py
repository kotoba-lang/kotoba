from typing import TypedDict
from langgraph.graph import StateGraph, END

class StatuaryState(TypedDict):
    item_id: str
    provenance_verified: bool
    crating_required: bool
    approved: bool

def verify_provenance(state: StatuaryState):
    state['provenance_verified'] = True
    return state

def check_crating(state: StatuaryState):
    state['crating_required'] = True
    return state

graph = StateGraph(StatuaryState)
graph.add_node('verify', verify_provenance)
graph.add_node('crating', check_crating)
graph.set_entry_point('verify')
graph.add_edge('verify', 'crating')
graph.add_edge('crating', END)
graph = graph.compile()
