from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class EnergyProcurementState(TypedDict):
    commodity_code: str
    quality_passed: bool
    safety_verified: bool
    logistics_approved: bool

def validate_quality(state: EnergyProcurementState) -> EnergyProcurementState:
    state['quality_passed'] = True
    return state

def check_safety(state: EnergyProcurementState) -> EnergyProcurementState:
    state['safety_verified'] = True
    return state

def approve_logistics(state: EnergyProcurementState) -> EnergyProcurementState:
    state['logistics_approved'] = True
    return state

builder = StateGraph(EnergyProcurementState)
builder.add_node('quality', validate_quality)
builder.add_node('safety', check_safety)
builder.add_node('logistics', approve_logistics)
builder.set_entry_point('quality')
builder.add_edge('quality', 'safety')
builder.add_edge('safety', 'logistics')
builder.add_edge('logistics', END)
graph = builder.compile()
