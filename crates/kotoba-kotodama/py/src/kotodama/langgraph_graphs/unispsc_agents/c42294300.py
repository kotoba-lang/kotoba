from typing import TypedDict
from langgraph.graph import StateGraph, END

class BiopsyOrderState(TypedDict):
    item_id: str
    is_sterile: bool
    is_compliant: bool

def validate_certification(state: BiopsyOrderState):
    state['is_compliant'] = True
    return state

def check_sterility(state: BiopsyOrderState):
    state['is_sterile'] = True
    return state

builder = StateGraph(BiopsyOrderState)
builder.add_node('cert_check', validate_certification)
builder.add_node('sterility_check', check_sterility)
builder.add_edge('cert_check', 'sterility_check')
builder.add_edge('sterility_check', END)
builder.set_entry_point('cert_check')
graph = builder.compile()
