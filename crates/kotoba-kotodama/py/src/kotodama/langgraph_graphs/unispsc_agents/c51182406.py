from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PharmState(TypedDict):
    batch_id: str
    compliance_cleared: bool
    quality_report: dict

def validate_quality(state: PharmState):
    # Simulate GMP compliance check
    return {'compliance_cleared': True}

def finalize_order(state: PharmState):
    return {'quality_report': {'status': 'approved'}}

builder = StateGraph(PharmState)
builder.add_node('validate', validate_quality)
builder.add_node('finalize', finalize_order)
builder.add_edge('validate', 'finalize')
builder.add_edge('finalize', END)
builder.set_entry_point('validate')
graph = builder.compile()
