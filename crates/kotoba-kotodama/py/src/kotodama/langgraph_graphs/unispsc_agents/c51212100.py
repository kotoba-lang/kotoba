from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DentalDrugState(TypedDict):
    drug_name: str
    regulatory_compliant: bool
    temp_valid: bool
    approval_status: str

def validate_drug(state: DentalDrugState):
    state['regulatory_compliant'] = state.get('approval_status') == 'Approved'
    return state

def check_storage(state: DentalDrugState):
    state['temp_valid'] = True
    return state

builder = StateGraph(DentalDrugState)
builder.add_node('validate', validate_drug)
builder.add_node('storage', check_storage)
builder.set_entry_point('validate')
builder.add_edge('validate', 'storage')
builder.add_edge('storage', END)
graph = builder.compile()
