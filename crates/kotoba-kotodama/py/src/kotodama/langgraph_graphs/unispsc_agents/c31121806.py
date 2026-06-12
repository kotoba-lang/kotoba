from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CastState(TypedDict):
    part_id: str
    material_spec: str
    tolerances_met: bool
    inspection_passed: bool

def validate_material(state: CastState) -> CastState:
    # Simulate material compliance check for ceramic mold castings
    state['material_spec'] = 'Alumina-Ceramic-Grade-A'
    return state

def check_tolerances(state: CastState) -> CastState:
    # Simulate CAD/Dimension validation
    state['tolerances_met'] = True
    return state

builder = StateGraph(CastState)
builder.add_node('validate', validate_material)
builder.add_node('inspect', check_tolerances)
builder.set_entry_point('validate')
builder.add_edge('validate', 'inspect')
builder.add_edge('inspect', END)
graph = builder.compile()
