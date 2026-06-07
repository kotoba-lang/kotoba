from typing import TypedDict
from langgraph.graph import StateGraph, END

class NeedleState(TypedDict):
    material: str
    gauge: float
    inspection_passed: bool

def validate_needle_specs(state: NeedleState) -> NeedleState:
    if state.get('gauge', 0) > 0 and state.get('material'):
        state['inspection_passed'] = True
    else:
        state['inspection_passed'] = False
    return state

builder = StateGraph(NeedleState)
builder.add_node('validate', validate_needle_specs)
builder.add_edge('validate', END)
builder.set_entry_point('validate')
graph = builder.compile()
