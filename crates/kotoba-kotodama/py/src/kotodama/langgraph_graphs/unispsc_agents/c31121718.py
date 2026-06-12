from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    part_id: str
    material_certified: bool
    dimensional_check_passed: bool
    ready_for_shipment: bool

def check_material(state: CastingState) -> CastingState:
    # Logic for verifying nickel alloy chemical composition
    state['material_certified'] = True
    return state

def validate_dimensions(state: CastingState) -> CastingState:
    # Logic for CAD vs physical measurement comparison
    state['dimensional_check_passed'] = True
    return state

builder = StateGraph(CastingState)
builder.add_node('material_audit', check_material)
builder.add_node('dim_check', validate_dimensions)
builder.set_entry_point('material_audit')
builder.add_edge('material_audit', 'dim_check')
builder.add_edge('dim_check', END)
graph = builder.compile()
