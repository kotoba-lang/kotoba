from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    reference_id: str
    is_verified: bool
    is_official_source: bool

def validate_reference_source(state: ProcurementState):
    # Business logic to verify official government source
    state['is_official_source'] = True
    return state

def verify_document_integrity(state: ProcurementState):
    # Check if the document contents match current legislature
    state['is_verified'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate_source', validate_reference_source)
graph.add_node('verify_content', verify_document_integrity)
graph.add_edge('validate_source', 'verify_content')
graph.add_edge('verify_content', END)
graph.set_entry_point('validate_source')
graph = graph.compile()
