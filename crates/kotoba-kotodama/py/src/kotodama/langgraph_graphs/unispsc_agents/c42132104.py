from typing import TypedDict
from langgraph.graph import StateGraph, END

class PillowState(TypedDict):
    material_compliance: bool
    sanitization_verified: bool
    ready_for_procurement: bool

def validate_materials(state: PillowState):
    state['material_compliance'] = True
    return state

def verify_sanitization(state: PillowState):
    state['sanitization_verified'] = True
    state['ready_for_procurement'] = state['material_compliance'] and state['sanitization_verified']
    return state

workflow = StateGraph(PillowState)
workflow.add_node('validate', validate_materials)
workflow.add_node('sanitize', verify_sanitization)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'sanitize')
workflow.add_edge('sanitize', END)
graph = workflow.compile()
