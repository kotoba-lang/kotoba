from typing import TypedDict
from langgraph.graph import StateGraph, END

class VendingState(TypedDict):
    vending_id: str
    haccp_verified: bool
    safety_check_passed: bool

def validate_haccp(state: VendingState):
    return {'haccp_verified': True}

def perform_safety_audit(state: VendingState):
    return {'safety_check_passed': True}

graph = StateGraph(VendingState)
graph.add_node('haccp_validation', validate_haccp)
graph.add_node('safety_audit', perform_safety_audit)
graph.set_entry_point('haccp_validation')
graph.add_edge('haccp_validation', 'safety_audit')
graph.add_edge('safety_audit', END)
graph = graph.compile()
