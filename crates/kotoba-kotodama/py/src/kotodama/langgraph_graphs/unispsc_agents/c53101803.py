from typing import TypedDict
from langgraph.graph import StateGraph, END

class GarmentState(TypedDict):
    material_compliance: bool
    safety_check_passed: bool
    final_approval: bool

def validate_materials(state: GarmentState):
    state['material_compliance'] = True
    return state

def check_safety_standards(state: GarmentState):
    state['safety_check_passed'] = True
    return state

def finalize_order(state: GarmentState):
    state['final_approval'] = state['material_compliance'] and state['safety_check_passed']
    return state

graph = StateGraph(GarmentState)
graph.add_node('validate', validate_materials)
graph.add_node('safety', check_safety_standards)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
