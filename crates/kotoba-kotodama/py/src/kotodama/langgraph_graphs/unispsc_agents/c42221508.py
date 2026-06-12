from typing import TypedDict
from langgraph.graph import StateGraph, END

class CatheterKitState(TypedDict):
    kit_id: str
    is_sterile: bool
    compliance_verified: bool

def validate_sterility(state: CatheterKitState):
    state['is_sterile'] = True
    return state

def verify_compliance(state: CatheterKitState):
    state['compliance_verified'] = True
    return state

graph = StateGraph(CatheterKitState)
graph.add_node('validate_sterility', validate_sterility)
graph.add_node('verify_compliance', verify_compliance)
graph.add_edge('validate_sterility', 'verify_compliance')
graph.add_edge('verify_compliance', END)
graph.set_entry_point('validate_sterility')
graph = graph.compile()
