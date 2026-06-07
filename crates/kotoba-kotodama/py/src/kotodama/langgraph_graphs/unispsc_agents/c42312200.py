from typing import TypedDict
from langgraph.graph import StateGraph, END

class SutureState(TypedDict):
    product_id: str
    is_sterile: bool
    compliance_score: float

def validate_sterility(state: SutureState):
    return {'is_sterile': True}

def check_compliance(state: SutureState):
    return {'compliance_score': 1.0 if state.get('is_sterile') else 0.0}

graph = StateGraph(SutureState)
graph.add_node('validate', validate_sterility)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
