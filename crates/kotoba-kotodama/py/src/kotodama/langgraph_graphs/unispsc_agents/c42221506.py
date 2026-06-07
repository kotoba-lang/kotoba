from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CatheterState(TypedDict):
    product_id: str
    compliance_docs: List[str]
    is_sterile: bool
    approved: bool

def validate_compliance(state: CatheterState):
    # Business logic for neonatal medical device validation
    certs = state.get('compliance_docs', [])
    state['approved'] = 'ISO13485' in certs and state.get('is_sterile', False)
    return state

def check_expiry(state: CatheterState):
    # Logic for regulatory shelf life verification
    return {'approved': state['approved']}

graph = StateGraph(CatheterState)
graph.add_node('validate', validate_compliance)
graph.add_node('expiry', check_expiry)
graph.set_entry_point('validate')
graph.add_edge('validate', 'expiry')
graph.add_edge('expiry', END)
graph = graph.compile()
