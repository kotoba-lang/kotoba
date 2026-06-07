from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class StorageState(TypedDict):
    dimensions: dict
    material: str
    compliance_docs: List[str]
    approved: bool

def validate_specs(state: StorageState):
    # Simulate CAD/Spec validation for panel storage
    is_valid = all([key in state for key in ['dimensions', 'material']])
    return {'approved': is_valid}

def check_compliance(state: StorageState):
    # Check for BIFMA certification tokens
    return {'approved': 'BIFMA' in state.get('compliance_docs', [])}

builder = StateGraph(StorageState)
builder.add_node('validate', validate_specs)
builder.add_node('compliance', check_compliance)
builder.set_entry_point('validate')
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
graph = builder.compile()
