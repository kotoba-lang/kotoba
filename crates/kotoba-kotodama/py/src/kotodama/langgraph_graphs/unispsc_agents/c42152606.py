from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    material_compliance: bool
    sterilization_verified: bool
    approved: bool

def validate_materials(state: DentalState):
    state['material_compliance'] = True
    return state

def check_sterilization(state: DentalState):
    state['sterilization_verified'] = True
    return state

def final_approval(state: DentalState):
    state['approved'] = state['material_compliance'] and state['sterilization_verified']
    return state

graph = StateGraph(DentalState)
graph.add_node('validate', validate_materials)
graph.add_node('sterilize', check_sterilization)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterilize')
graph.add_edge('sterilize', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
