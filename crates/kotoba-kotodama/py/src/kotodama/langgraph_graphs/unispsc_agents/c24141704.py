from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    content: str
    compliance_score: float
    layout_approved: bool

def validate_content(state: ProcurementState):
    print('Validating instructional content accuracy...')
    return {'compliance_score': 1.0}

def check_layout(state: ProcurementState):
    print('Verifying layout and readability specs...')
    return {'layout_approved': True}

builder = StateGraph(ProcurementState)
builder.add_node('validate', validate_content)
builder.add_node('check_layout', check_layout)
builder.add_edge('validate', 'check_layout')
builder.add_edge('check_layout', END)
builder.set_entry_point('validate')
graph = builder.compile()
