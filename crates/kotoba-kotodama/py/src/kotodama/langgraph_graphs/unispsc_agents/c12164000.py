from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    commodity_code: str
    batch_id: str
    purity_check: bool
    safety_clearance: bool
    approved: bool

def validate_purity(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Simulate purity validation logic
    state['purity_check'] = True
    return state

def check_safety_compliance(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Simulate safety compliance logic
    state['safety_clearance'] = True
    return state

def finalize_order(state: ChemicalProcurementState) -> ChemicalProcurementState:
    state['approved'] = state['purity_check'] and state['safety_clearance']
    return state

builder = StateGraph(ChemicalProcurementState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('check_safety', check_safety_compliance)
builder.add_node('finalize', finalize_order)
builder.set_entry_point('validate_purity')
builder.add_edge('validate_purity', 'check_safety')
builder.add_edge('check_safety', 'finalize')
builder.add_edge('finalize', END)
graph = builder.compile()
