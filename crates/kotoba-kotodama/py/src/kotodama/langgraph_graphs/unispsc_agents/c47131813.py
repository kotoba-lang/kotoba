from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CleaningProductState(TypedDict):
    product_id: str
    msds_verified: bool
    safety_check_passed: bool

def verify_msds_compliance(state: CleaningProductState):
    # Simulate chemical safety validation
    return {'msds_verified': True}

def perform_safety_check(state: CleaningProductState):
    # Simulate surface compatibility validation
    return {'safety_check_passed': True}

graph = StateGraph(CleaningProductState)
graph.add_node('verify_msds', verify_msds_compliance)
graph.add_node('safety_check', perform_safety_check)
graph.add_edge('verify_msds', 'safety_check')
graph.add_edge('safety_check', END)
graph.set_entry_point('verify_msds')
graph = graph.compile()
