from typing import TypedDict
from langgraph.graph import StateGraph, END

class SutureKitState(TypedDict):
    kit_id: str
    is_sterile: bool
    compliance_verified: bool

def validate_sterilization(state: SutureKitState) -> SutureKitState:
    state['is_sterile'] = True
    return state

def check_compliance(state: SutureKitState) -> SutureKitState:
    state['compliance_verified'] = True
    return state

graph = StateGraph(SutureKitState)
graph.add_node('validate', validate_sterilization)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
