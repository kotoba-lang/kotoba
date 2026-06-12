from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    product_id: str
    compliance_checked: bool
    approved: bool

def validate_material(state: DentalState):
    # Simulate material compliance check for medical device classification
    state['compliance_checked'] = True
    return state

def approve_procurement(state: DentalState):
    state['approved'] = True
    return state

graph = StateGraph(DentalState)
graph.add_node('validate_material', validate_material)
graph.add_node('approve_procurement', approve_procurement)
graph.add_edge('validate_material', 'approve_procurement')
graph.add_edge('approve_procurement', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
