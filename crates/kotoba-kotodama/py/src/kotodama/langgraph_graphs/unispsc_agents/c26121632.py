from typing import TypedDict
from langgraph.graph import StateGraph, END

class OSPState(TypedDict):
    cable_specs: dict
    validation_log: list
    is_approved: bool

def validate_specs(state: OSPState):
    specs = state.get('cable_specs', {})
    log = []
    if 'jacket_material' not in specs: log.append('Missing jacket material')
    if 'tensile_strength' not in specs: log.append('Missing tensile strength')
    return {'validation_log': log, 'is_approved': len(log) == 0}

builder = StateGraph(OSPState)
builder.add_node('validate', validate_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
