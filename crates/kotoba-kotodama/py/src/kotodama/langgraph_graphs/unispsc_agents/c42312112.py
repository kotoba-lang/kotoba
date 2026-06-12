from typing import TypedDict
from langgraph.graph import StateGraph, END

class OstomyProcurementState(TypedDict):
    product_id: str
    compliance_docs: list
    is_approved: bool

def validate_compliance(state: OstomyProcurementState):
    state['is_approved'] = len(state.get('compliance_docs', [])) >= 3
    return state

def route_verification(state: OstomyProcurementState):
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(OstomyProcurementState)
graph.add_node('validate', validate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
