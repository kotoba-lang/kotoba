from typing import TypedDict
from langgraph.graph import StateGraph, END

class CompressorState(TypedDict):
    part_number: str
    spec_valid: bool
    approved: bool

def validate_specs(state: CompressorState):
    state['spec_valid'] = bool(state.get('part_number'))
    return state

def route_review(state: CompressorState):
    return 'approve' if state['spec_valid'] else END

builder = StateGraph(CompressorState)
builder.add_node('validate', validate_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
