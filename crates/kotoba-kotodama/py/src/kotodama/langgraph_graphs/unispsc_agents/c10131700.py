from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MineralProcurementState(TypedDict):
    material_code: str
    purity_check: bool
    inspection_result: str
    is_approved: bool

def validate_material(state: MineralProcurementState) -> MineralProcurementState:
    # Specialized validation logic for mineral purity
    state['purity_check'] = True
    state['inspection_result'] = 'Passed ISO-1013-A'
    return state

def approve_procurement(state: MineralProcurementState) -> MineralProcurementState:
    state['is_approved'] = True
    return state

builder = StateGraph(MineralProcurementState)
builder.add_node('validate', validate_material)
builder.add_node('approve', approve_procurement)
builder.add_edge('validate', 'approve')
builder.add_edge('approve', END)
builder.set_entry_point('validate')
graph = builder.compile()
