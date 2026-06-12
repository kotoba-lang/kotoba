from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalProductState(TypedDict):
    product_id: str
    compliance_checked: bool
    safety_score: float

def validate_compliance(state: DentalProductState):
    # Simulate regulatory validation for medical grade pastes
    state['compliance_checked'] = True
    return state

def assess_safety(state: DentalProductState):
    # Simulate safety protocol check
    state['safety_score'] = 0.95
    return state

graph = StateGraph(DentalProductState)
graph.add_node('validate', validate_compliance)
graph.add_node('safety', assess_safety)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
