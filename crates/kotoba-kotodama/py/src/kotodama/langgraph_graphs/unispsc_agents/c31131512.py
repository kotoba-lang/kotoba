from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    spec_compliance: bool
    metallurgical_report: str
    approval_status: str

def validate_specs(state: ForgingState):
    state['spec_compliance'] = True
    return {'approval_status': 'Validated'}

def check_quality(state: ForgingState):
    state['metallurgical_report'] = 'Grade A Certified'
    return {'approval_status': 'Inspected'}

builder = StateGraph(ForgingState)
builder.add_node('validate', validate_specs)
builder.add_node('quality', check_quality)
builder.add_edge('validate', 'quality')
builder.set_entry_point('validate')
builder.add_edge('quality', END)
graph = builder.compile()
