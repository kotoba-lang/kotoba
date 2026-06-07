from typing import TypedDict
from langgraph.graph import StateGraph, END
class IABPState(TypedDict):
    device_id: str
    compliance_docs: list
    validation_status: bool

def validate_compliance(state: IABPState):
    docs = state.get('compliance_docs', [])
    is_valid = 'ISO_13485' in docs and 'CE_Cert' in docs
    return {'validation_status': is_valid}

def route_verification(state: IABPState):
    return 'success' if state['validation_status'] else 'manual_review'

graph = StateGraph(IABPState)
graph.add_node('validate', validate_compliance)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
