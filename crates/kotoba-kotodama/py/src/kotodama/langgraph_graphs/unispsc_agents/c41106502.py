from typing import TypedDict
from langgraph.graph import StateGraph, END

class TransfectionState(TypedDict):
    reagent_id: str
    batch_number: str
    temp_validation: bool
    is_approved: bool

def validate_cold_chain(state: TransfectionState):
    # Simulate cold chain validation check
    return {'temp_validation': True}

def approve_procurement(state: TransfectionState):
    return {'is_approved': state['temp_validation']}

builder = StateGraph(TransfectionState)
builder.add_node('validate', validate_cold_chain)
builder.add_node('approve', approve_procurement)
builder.add_edge('validate', 'approve')
builder.add_edge('approve', END)
builder.set_entry_point('validate')
graph = builder.compile()
