from typing import TypedDict
from langgraph.graph import StateGraph, END

class StampState(TypedDict):
    order_id: str
    material_safety_verified: bool
    design_validation: bool

def validate_materials(state: StampState):
    print('Verifying chemical safety for rubber and ink')
    return {'material_safety_verified': True}

def validate_design(state: StampState):
    print('Validating stamp impression clarity and scale')
    return {'design_validation': True}

builder = StateGraph(StampState)
builder.add_node('safety_check', validate_materials)
builder.add_node('design_check', validate_design)
builder.set_entry_point('safety_check')
builder.add_edge('safety_check', 'design_check')
builder.add_edge('design_check', END)
graph = builder.compile()
