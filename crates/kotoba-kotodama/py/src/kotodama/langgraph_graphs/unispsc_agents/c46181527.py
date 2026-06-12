from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material: str
    compliance_docs: bool
    is_approved: bool

def check_compliance(state: ProcurementState):
    state['is_approved'] = state.get('compliance_docs', False) and 'flame_resistant' in state.get('material', '').lower()
    return state

builder = StateGraph(ProcurementState)
builder.add_node('validate', check_compliance)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
