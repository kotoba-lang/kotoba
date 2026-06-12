from typing import TypedDict
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    material_type: str
    compliance_docs: list
    is_approved: bool

def validate_certification(state: ResinState):
    # Business logic for dental resin certification
    docs = state.get('compliance_docs', [])
    is_valid = 'ISO_4049' in docs and 'SDS' in docs
    return {'is_approved': is_valid}

def route_by_type(state: ResinState):
    return 'validate_certification'

graph = StateGraph(ResinState)
graph.add_node('validate', validate_certification)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
