from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CutleryState(TypedDict):
    item_name: str
    material_compliance: bool
    safety_check: bool
    approved: bool

def validate_material(state: CutleryState):
    # logic to check IF stainless steel quality meets commercial food standards
    state['material_compliance'] = True
    return state

def check_safety(state: CutleryState):
    # logic for NSF or food-contact certification verification
    state['safety_check'] = True
    return state

builder = StateGraph(CutleryState)
builder.add_node('validate', validate_material)
builder.add_node('safety', check_safety)
builder.set_entry_point('validate')
builder.add_edge('validate', 'safety')
builder.add_edge('safety', END)
graph = builder.compile()
