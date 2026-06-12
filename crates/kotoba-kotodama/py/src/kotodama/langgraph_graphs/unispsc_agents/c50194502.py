from typing import TypedDict
from langgraph.graph import StateGraph, END

class FoodProcurementState(TypedDict):
    quality_score: float
    compliance_checked: bool

def validate_purity(state: FoodProcurementState):
    state['quality_score'] = 1.0
    return state

def check_compliance(state: FoodProcurementState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(FoodProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
