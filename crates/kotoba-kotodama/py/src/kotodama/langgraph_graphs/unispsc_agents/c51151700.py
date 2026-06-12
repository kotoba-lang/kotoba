from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    batch_id: str
    compliance_cleared: bool
    temp_log_verified: bool

def validate_batch(state: DrugProcurementState):
    # Simulate regulatory validation
    state['compliance_cleared'] = state.get('batch_id').startswith('B-')
    return state

def check_cold_chain(state: DrugProcurementState):
    # Simulate cold chain audit
    state['temp_log_verified'] = True
    return state

builder = StateGraph(DrugProcurementState)
builder.add_node('validate', validate_batch)
builder.add_node('cold_chain', check_cold_chain)
builder.add_edge('validate', 'cold_chain')
builder.add_edge('cold_chain', END)
builder.set_entry_point('validate')
graph = builder.compile()
