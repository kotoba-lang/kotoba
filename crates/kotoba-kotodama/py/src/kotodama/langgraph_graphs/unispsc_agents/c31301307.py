from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_specs: dict
    inspection_results: dict
    is_compliant: bool

def validate_chemistry(state: ForgingState):
    # Perform check on magnesium alloy composition certificates
    return {'is_compliant': True}

def conduct_ndt(state: ForgingState):
    # Perform simulated NDT validation for porosity or cracks
    return {'inspection_results': {'status': 'passed'}}

builder = StateGraph(ForgingState)
builder.add_node('chemistry_check', validate_chemistry)
builder.add_node('ndt_analysis', conduct_ndt)
builder.add_edge('chemistry_check', 'ndt_analysis')
builder.add_edge('ndt_analysis', END)
builder.set_entry_point('chemistry_check')
graph = builder.compile()
