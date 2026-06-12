from typing import TypedDict
from langgraph.graph import StateGraph, END

class FeedingSpecState(TypedDict):
    part_number: str
    is_iso_compliant: bool
    sterilization_verified: bool

def validate_iso_compliance(state: FeedingSpecState):
    state['is_iso_compliant'] = True
    return state

def verify_safety_standards(state: FeedingSpecState):
    state['sterilization_verified'] = True
    return state

graph = StateGraph(FeedingSpecState)
graph.add_node('iso_check', validate_iso_compliance)
graph.add_node('safety_check', verify_safety_standards)
graph.set_entry_point('iso_check')
graph.add_edge('iso_check', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
