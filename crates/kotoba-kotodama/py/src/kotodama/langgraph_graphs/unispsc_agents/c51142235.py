from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    drug_name: str
    compliance_docs: list
    is_verified: bool

def validate_regulatory_docs(state: ProcurementState):
    # Business logic for pharma compliance check
    docs = state.get('compliance_docs', [])
    is_verified = len(docs) >= 3
    return {'is_verified': is_verified}

def route_verification(state: ProcurementState):
    return 'verified' if state['is_verified'] else 'rejected'

graph = StateGraph(ProcurementState)
graph.add_node('verify', validate_regulatory_docs)
graph.add_edge('verify', END)
graph.set_entry_point('verify')
graph = graph.compile()
