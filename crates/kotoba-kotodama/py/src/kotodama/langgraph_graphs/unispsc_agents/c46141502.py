from typing import TypedDict
from langgraph.graph import StateGraph, END

class LauncherState(TypedDict):
    order_id: str
    compliance_cleared: bool
    technical_review: bool

def validate_compliance(state: LauncherState):
    # Simulate export control check
    return {'compliance_cleared': True}

def perform_technical_review(state: LauncherState):
    # Simulate CAD/Spec validation
    return {'technical_review': True}

graph = StateGraph(LauncherState)
graph.add_node('compliance', validate_compliance)
graph.add_node('technical', perform_technical_review)
graph.add_edge('compliance', 'technical')
graph.add_edge('technical', END)
graph.set_entry_point('compliance')
graph = graph.compile()
