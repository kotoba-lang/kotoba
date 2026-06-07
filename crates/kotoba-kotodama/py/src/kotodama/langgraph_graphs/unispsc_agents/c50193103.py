from typing import TypedDict
from langgraph.graph import StateGraph, END

class GravyWorkflowState(TypedDict):
    brand: str
    expiry_date: str
    safety_compliant: bool
    approved: bool

def validate_food_safety(state: GravyWorkflowState):
    # Business logic for gravy safety inspection
    state['safety_compliant'] = True
    print('Safety validation passed.')
    return state

def approve_procurement(state: GravyWorkflowState):
    state['approved'] = state['safety_compliant']
    return state

graph = StateGraph(GravyWorkflowState)
graph.add_node('safety_check', validate_food_safety)
graph.add_node('approval', approve_procurement)
graph.add_edge('safety_check', 'approval')
graph.add_edge('approval', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
