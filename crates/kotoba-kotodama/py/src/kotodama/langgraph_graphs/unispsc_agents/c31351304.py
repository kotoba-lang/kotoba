from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_number: str
    material_certified: bool
    geometric_tolerance_passed: bool
    ndt_clearance: bool

def validate_specs(state: ProcurementState):
    # Simulate CAD and material requirement check
    state['material_certified'] = True
    state['geometric_tolerance_passed'] = True
    return state

def perform_ndt_check(state: ProcurementState):
    state['ndt_clearance'] = True
    return state

builder = StateGraph(ProcurementState)
builder.add_node('validate', validate_specs)
builder.add_node('ndt', perform_ndt_check)
builder.add_edge('validate', 'ndt')
builder.add_edge('ndt', END)
builder.set_entry_point('validate')
graph = builder.compile()
