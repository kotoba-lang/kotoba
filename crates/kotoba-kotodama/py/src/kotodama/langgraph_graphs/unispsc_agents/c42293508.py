from typing import TypedDict
from langgraph.graph import StateGraph, END

class ENTSupplyState(TypedDict):
    part_number: str
    is_sterile: bool
    compliance_docs: list
    approval_status: str

def validate_sterility(state: ENTSupplyState):
    state['is_sterile'] = True if state.get('compliance_docs') else False
    return state

def verify_compliance(state: ENTSupplyState):
    state['approval_status'] = 'APPROVED' if state['is_sterile'] else 'REJECTED'
    return state

graph = StateGraph(ENTSupplyState)
graph.add_node('validate', validate_sterility)
graph.add_node('verify', verify_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()
