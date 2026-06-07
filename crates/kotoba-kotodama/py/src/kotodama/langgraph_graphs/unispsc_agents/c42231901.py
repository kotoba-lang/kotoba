from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    device_id: str
    compliance_docs: list
    is_verified: bool

def validate_medical_compliance(state: PumpState):
    state['is_verified'] = len(state.get('compliance_docs', [])) >= 2
    return state

def route_verification(state: PumpState):
    return 'verified' if state['is_verified'] else 'rejected'

graph = StateGraph(PumpState)
graph.add_node('validate', validate_medical_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
