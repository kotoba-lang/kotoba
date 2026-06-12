from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class IncubationState(TypedDict):
    batch_id: str
    status: str
    health_checks: List[str]
    compliance_passed: bool

def validate_batch(state: IncubationState):
    return {status: 'VALIDATING'}

def check_biosecurity(state: IncubationState):
    passed = len(state.get('health_checks', [])) > 0
    return {compliance_passed: passed, status: 'CHECKED'}

builder = StateGraph(IncubationState)
builder.add_node('validate', validate_batch)
builder.add_node('biosecurity', check_biosecurity)
builder.set_entry_point('validate')
builder.add_edge('validate', 'biosecurity')
builder.add_edge('biosecurity', END)
graph = builder.compile()
