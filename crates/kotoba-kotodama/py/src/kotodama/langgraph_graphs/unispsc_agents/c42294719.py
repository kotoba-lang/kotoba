from typing import TypedDict
from langgraph.graph import StateGraph, END

class ReservoirState(TypedDict):
    sterility_checked: bool
    compliance_validated: bool
    batch_number: str

def check_sterility(state: ReservoirState):
    state['sterility_checked'] = True
    return state

def validate_compliance(state: ReservoirState):
    state['compliance_validated'] = True
    return state

builder = StateGraph(ReservoirState)
builder.add_node('check_sterility', check_sterility)
builder.add_node('validate_compliance', validate_compliance)
builder.set_entry_point('check_sterility')
builder.add_edge('check_sterility', 'validate_compliance')
builder.add_edge('validate_compliance', END)
graph = builder.compile()
