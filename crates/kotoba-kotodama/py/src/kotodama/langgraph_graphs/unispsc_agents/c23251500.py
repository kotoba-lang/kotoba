from typing import TypedDict
from langgraph.graph import StateGraph, END

class BendingMachineState(TypedDict):
    spec_data: dict
    safety_check: bool
    is_approved: bool

def validate_specs(state: BendingMachineState):
    specs = state.get('spec_data', {})
    state['safety_check'] = 'safety_light_curtain_certification' in specs
    return state

def approval_check(state: BendingMachineState):
    state['is_approved'] = state.get('safety_check', False)
    return state

builder = StateGraph(BendingMachineState)
builder.add_node('validate', validate_specs)
builder.add_node('approve', approval_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'approve')
builder.add_edge('approve', END)
graph = builder.compile()
