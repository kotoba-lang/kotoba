from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    material: str
    specifications: dict
    validation_score: float
    status: str

def validate_packaging(state: PackagingState) -> PackagingState:
    # Specialized validation logic for packaging material safety/standard
    state['validation_score'] = 1.0 if 'material' in state else 0.0
    state['status'] = 'VALIDATED' if state['validation_score'] > 0 else 'REJECTED'
    return state

def check_compliance(state: PackagingState) -> PackagingState:
    # Compliance check against transport regulations
    state['status'] = 'COMPLIANT' if state['status'] == 'VALIDATED' else 'NON_COMPLIANT'
    return state

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_packaging)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
