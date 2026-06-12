from typing import TypedDict
from langgraph.graph import StateGraph, END

class InhalatorState(TypedDict):
    device_id: str
    compliance_verified: bool
    safety_check_passed: bool

def validate_compliance(state: InhalatorState):
    return {'compliance_verified': True}

def perform_safety_check(state: InhalatorState):
    return {'safety_check_passed': True}

graph = StateGraph(InhalatorState)
graph.add_node('validate', validate_compliance)
graph.add_node('safety', perform_safety_check)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()
