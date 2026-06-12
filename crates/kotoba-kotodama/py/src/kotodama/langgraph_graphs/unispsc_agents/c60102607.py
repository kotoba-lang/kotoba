from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    safety_verified: bool
    compliance_score: float

def validate_educational_specs(state: ProcurementState):
    # Simulate validation logic for educational material compliance
    state['safety_verified'] = True
    state['compliance_score'] = 1.0
    return state

def approve_procurement(state: ProcurementState):
    return state

builder = StateGraph(ProcurementState)
builder.add_node('validate', validate_educational_specs)
builder.add_node('approve', approve_procurement)
builder.add_edge('validate', 'approve')
builder.set_entry_point('validate')
builder.add_edge('approve', END)
graph = builder.compile()
