from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    spec: dict
    validated: bool
    error: str

def validate_spec(state: PumpState) -> PumpState:
    spec = state.get('spec', {})
    # Check for mandatory technical specs for sludge pumps
    required = ['max_flow_rate_m3h', 'solid_handling_capacity_mm']
    if all(k in spec for k in required):
        state['validated'] = True
    else:
        state['validated'] = False
        state['error'] = 'Missing critical sludge pump parameters'
    return state

builder = StateGraph(PumpState)
builder.add_node('validate', validate_spec)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
