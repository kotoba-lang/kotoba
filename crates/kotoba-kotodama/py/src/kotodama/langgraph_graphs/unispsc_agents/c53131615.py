from typing import TypedDict
from langgraph.graph import StateGraph, END

class HygieneProductState(TypedDict):
    product_id: str
    compliance_docs: list
    is_approved: bool

def validate_safety_certs(state: HygieneProductState):
    state['is_approved'] = all('ISO' in doc or 'FDA' in doc for doc in state.get('compliance_docs', []))
    return state

def check_shelf_life(state: HygieneProductState):
    # Business logic for expiration checks
    return {'is_approved': state['is_approved'] and True}

graph = StateGraph(HygieneProductState)
graph.add_node('safety_check', validate_safety_certs)
graph.add_node('expiry_check', check_shelf_life)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'expiry_check')
graph.add_edge('expiry_check', END)
graph = graph.compile()
