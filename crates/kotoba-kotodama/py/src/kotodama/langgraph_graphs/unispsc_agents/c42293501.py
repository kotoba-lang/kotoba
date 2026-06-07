from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalSupplyState(TypedDict):
    part_number: str
    is_sterile: bool
    regulatory_compliant: bool

def validate_specs(state: SurgicalSupplyState):
    if not state.get('is_sterile'):
        state['regulatory_compliant'] = False
    else:
        state['regulatory_compliant'] = True
    return state

builder = StateGraph(SurgicalSupplyState)
builder.add_node('validate', validate_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
