from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TherapyState(TypedDict):
    device_type: str
    iso_compliance: bool
    safety_check: bool

def validate_compliance(state: TherapyState):
    state['iso_compliance'] = True
    return state

def safety_review(state: TherapyState):
    state['safety_check'] = True
    return state

builder = StateGraph(TherapyState)
builder.add_node('compliance', validate_compliance)
builder.add_node('safety', safety_review)
builder.add_edge('compliance', 'safety')
builder.add_edge('safety', END)
builder.set_entry_point('compliance')
graph = builder.compile()
