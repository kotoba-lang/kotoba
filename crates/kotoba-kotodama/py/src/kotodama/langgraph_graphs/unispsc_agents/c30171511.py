from typing import TypedDict
from langgraph.graph import StateGraph, END

class DoorProcurementState(TypedDict):
    material_spec: str
    dimensions: dict
    compliance_check: bool

def validate_specs(state: DoorProcurementState):
    state['compliance_check'] = 'fire_rating' in state.get('material_spec', '').lower()
    return state

builder = StateGraph(DoorProcurementState)
builder.add_node('validate', validate_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
