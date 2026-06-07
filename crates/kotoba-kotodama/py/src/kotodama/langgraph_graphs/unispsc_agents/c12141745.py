from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    material_id: str
    purity_check: bool
    safety_cleared: bool
    status: str

def validate_material_purity(state: MaterialState) -> MaterialState:
    # Logic to verify material purity against standards
    state['purity_check'] = True
    return state

def check_safety_compliance(state: MaterialState) -> MaterialState:
    # Logic for MSDS and dangerous goods clearance
    state['safety_cleared'] = True
    return state

builder = StateGraph(MaterialState)
builder.add_node('validate', validate_material_purity)
builder.add_node('safety', check_safety_compliance)
builder.add_edge('validate', 'safety')
builder.add_edge('safety', END)
builder.set_entry_point('validate')
graph = builder.compile()
