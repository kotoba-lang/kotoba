from langgraph.graph import StateGraph, END
from typing import TypedDict
class DeflectorState(TypedDict):
    compatibility_checked: bool
    aerodynamic_approved: bool
    final_procurement_data: dict
def check_compatibility(state: DeflectorState):
    state['compatibility_checked'] = True
    return state
def validate_aerodynamics(state: DeflectorState):
    state['aerodynamic_approved'] = True
    return state
graph = StateGraph(DeflectorState)
graph.add_node('check_compatibility', check_compatibility)
graph.add_node('validate_aerodynamics', validate_aerodynamics)
graph.set_entry_point('check_compatibility')
graph.add_edge('check_compatibility', 'validate_aerodynamics')
graph.add_edge('validate_aerodynamics', END)
graph = graph.compile()
