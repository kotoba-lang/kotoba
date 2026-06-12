from typing import TypedDict
from langgraph.graph import StateGraph, END

class LampState(TypedDict):
    material_check: bool
    safety_seal_passed: bool
    is_approved: bool

def validate_materials(state: LampState) -> LampState:
    state['material_check'] = True
    return state

def check_safety_seal(state: LampState) -> LampState:
    state['safety_seal_passed'] = True
    return state

builder = StateGraph(LampState)
builder.add_node('validate', validate_materials)
builder.add_node('safety', check_safety_seal)
builder.add_edge('validate', 'safety')
builder.add_edge('safety', END)
builder.set_entry_point('validate')
graph = builder.compile()
