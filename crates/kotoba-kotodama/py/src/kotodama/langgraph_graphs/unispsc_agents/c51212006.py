from typing import TypedDict
from langgraph.graph import StateGraph, END

class ValerianState(TypedDict):
    batch_id: str
    purity_check: bool
    safety_report: dict
    approved: bool

def validate_purity(state: ValerianState):
    # logic to inspect purity levels
    return {'purity_check': True}

def check_safety_standards(state: ValerianState):
    # check for heavy metals and pesticides
    return {'safety_report': {'status': 'passed'}}

builder = StateGraph(ValerianState)
builder.add_node('purity', validate_purity)
builder.add_node('safety', check_safety_standards)
builder.set_entry_point('purity')
builder.add_edge('purity', 'safety')
builder.add_edge('safety', END)
graph = builder.compile()
