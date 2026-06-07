from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    product_id: str
    iso_compliance: bool
    sterility_check: bool
    approval_status: str

def validate_standards(state: DentalState):
    state['iso_compliance'] = True
    return state

def inspect_sterility(state: DentalState):
    state['sterility_check'] = True if state['iso_compliance'] else False
    return state

def final_approval(state: DentalState):
    state['approval_status'] = 'APPROVED' if state['sterility_check'] else 'REJECTED'
    return state

graph = StateGraph(DentalState)
graph.add_node('validate', validate_standards)
graph.add_node('inspect', inspect_sterility)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
