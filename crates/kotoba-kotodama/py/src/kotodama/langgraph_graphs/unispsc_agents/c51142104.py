from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmaProcurementState(TypedDict):
    batch_id: str
    quality_docs_verified: bool
    compliance_cleared: bool

def check_quality_docs(state: PharmaProcurementState):
    state['quality_docs_verified'] = True
    return state

def verify_compliance(state: PharmaProcurementState):
    state['compliance_cleared'] = True
    return state

graph = StateGraph(PharmaProcurementState)
graph.add_node('verify_docs', check_quality_docs)
graph.add_node('compliance', verify_compliance)
graph.set_entry_point('verify_docs')
graph.add_edge('verify_docs', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
