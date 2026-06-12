from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClothingState(TypedDict):
    material_certified: bool
    safety_check_passed: bool
    procurement_approved: bool

def validate_material(state: ClothingState):
    state['material_certified'] = True
    return state

def check_safety(state: ClothingState):
    state['safety_check_passed'] = True
    return state

workflow = StateGraph(ClothingState)
workflow.add_node('validate_material', validate_material)
workflow.add_node('check_safety', check_safety)
workflow.set_entry_point('validate_material')
workflow.add_edge('validate_material', 'check_safety')
workflow.add_edge('check_safety', END)
graph = workflow.compile()
