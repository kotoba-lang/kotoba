from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    purity_check: bool
    hazard_verified: bool
    procurement_approved: bool

def validate_purity(state: ChemicalState):
    # Simulate purity validation against spec_fields
    return {**state, 'purity_check': True}

def verify_hazard(state: ChemicalState):
    # Simulate safety compliance check
    return {**state, 'hazard_verified': True}

def approve_procurement(state: ChemicalState):
    # Logic for final procurement sign-off
    approved = state['purity_check'] and state['hazard_verified']
    return {**state, 'procurement_approved': approved}

builder = StateGraph(ChemicalState)
builder.add_node('validate', validate_purity)
builder.add_node('hazard', verify_hazard)
builder.add_node('approve', approve_procurement)

builder.set_entry_point('validate')
builder.add_edge('validate', 'hazard')
builder.add_edge('hazard', 'approve')
builder.add_edge('approve', END)

graph = builder.compile()
