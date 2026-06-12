from langgraph.graph import StateGraph, END
from typing import TypedDict
class ForgingState(TypedDict):
    material_certified: bool
    geometric_check: bool
    heat_treatment_verified: bool
    approved: bool
def validate_metallurgy(state: ForgingState):
    state['material_certified'] = True
    return state
def perform_dimensional_inspection(state: ForgingState):
    state['geometric_check'] = True
    return state
def verify_process_compliance(state: ForgingState):
    state['heat_treatment_verified'] = True
    state['approved'] = all([state['material_certified'], state['geometric_check'], state['heat_treatment_verified']])
    return state
graph = StateGraph(ForgingState)
graph.add_node('metallurgy', validate_metallurgy)
graph.add_node('geometry', perform_dimensional_inspection)
graph.add_node('compliance', verify_process_compliance)
graph.set_entry_point('metallurgy')
graph.add_edge('metallurgy', 'geometry')
graph.add_edge('geometry', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
