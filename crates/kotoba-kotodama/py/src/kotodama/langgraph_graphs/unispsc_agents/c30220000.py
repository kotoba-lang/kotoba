from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class StructureState(TypedDict):
    specs: dict
    validated: bool
    permits: List[str]

def validate_structural_specs(state: StructureState):
    specs = state.get('specs', {})
    is_valid = all(k in specs for k in ['load', 'material', 'safety_code'])
    return {'validated': is_valid}

def check_permits(state: StructureState):
    return {'permits': ['approved'] if state.get('validated') else ['pending']}

builder = StateGraph(StructureState)
builder.add_node('validate', validate_structural_specs)
builder.add_node('permit', check_permits)
builder.set_entry_point('validate')
builder.add_edge('validate', 'permit')
builder.add_edge('permit', END)
graph = builder.compile()
