from typing import TypedDict
from langgraph.graph import StateGraph, END

class OrsState(TypedDict):
    batch_id: str
    purity_validated: bool
    expiry_check: bool

def validate_batch(state: OrsState):
    return {'purity_validated': True}

def check_expiry(state: OrsState):
    return {'expiry_check': True}

graph = StateGraph(OrsState)
graph.add_node('validate', validate_batch)
graph.add_node('expiry', check_expiry)
graph.set_entry_point('validate')
graph.add_edge('validate', 'expiry')
graph.add_edge('expiry', END)
graph = graph.compile()
