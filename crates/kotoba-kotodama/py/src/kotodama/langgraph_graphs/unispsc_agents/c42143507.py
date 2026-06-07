from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    product_id: str
    is_sterile: bool
    compliance_verified: bool

def validate_sterility(state: State) -> State:
    state['is_sterile'] = True
    return state

def check_compliance(state: State) -> State:
    state['compliance_verified'] = True
    return state

graph = StateGraph(State)
graph.add_node('validate', validate_sterility)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
