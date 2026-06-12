from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ChemicalProcurementState(TypedDict):
    commodity_id: str
    purity_check: bool
    safety_compliance: List[str]
    approval_status: str

def validate_purity(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Logic to verify purity against specs
    state['purity_check'] = True
    return state

def check_safety_compliance(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Logic to check GHS hazards and export controls
    state['safety_compliance'] = ['GHS-OK', 'Export-Clear']
    return state

def finalize_order(state: ChemicalProcurementState) -> ChemicalProcurementState:
    state['approval_status'] = 'READY'
    return state

builder = StateGraph(ChemicalProcurementState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('check_safety_compliance', check_safety_compliance)
builder.add_node('finalize_order', finalize_order)

builder.set_entry_point('validate_purity')
builder.add_edge('validate_purity', 'check_safety_compliance')
builder.add_edge('check_safety_compliance', 'finalize_order')
builder.add_edge('finalize_order', END)

graph = builder.compile()
