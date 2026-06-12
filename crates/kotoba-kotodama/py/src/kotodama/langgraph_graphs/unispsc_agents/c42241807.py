from typing import TypedDict
from langgraph.graph import StateGraph, END

class OrthopedicState(TypedDict):
    product_id: str
    compliance_verified: bool
    safety_check_passed: bool

def validate_compliance(state: OrthopedicState):
    state['compliance_verified'] = True
    return state

def check_biocompatibility(state: OrthopedicState):
    state['safety_check_passed'] = True
    return state

graph = StateGraph(OrthopedicState)
graph.add_node('validate', validate_compliance)
graph.add_node('safety', check_biocompatibility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
