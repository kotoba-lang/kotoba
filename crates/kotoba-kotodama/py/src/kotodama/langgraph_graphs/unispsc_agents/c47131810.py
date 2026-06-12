from typing import TypedDict
from langgraph.graph import StateGraph, END

class DishwashState(TypedDict):
    product_name: str
    sds_verified: bool
    compliance_score: float

def validate_sds(state: DishwashState) -> DishwashState:
    state['sds_verified'] = True if state.get('product_name') else False
    return state

def assess_compliance(state: DishwashState) -> DishwashState:
    state['compliance_score'] = 1.0 if state['sds_verified'] else 0.0
    return state

graph = StateGraph(DishwashState)
graph.add_node('validate_sds', validate_sds)
graph.add_node('assess_compliance', assess_compliance)
graph.set_entry_point('validate_sds')
graph.add_edge('validate_sds', 'assess_compliance')
graph.add_edge('assess_compliance', END)

graph = graph.compile()
