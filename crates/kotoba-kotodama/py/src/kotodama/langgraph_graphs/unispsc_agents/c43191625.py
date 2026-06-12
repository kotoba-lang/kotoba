from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class DesktopState(TypedDict):
    specs: dict
    validation_results: list
    status: str

def validate_specs(state: DesktopState) -> DesktopState:
    specs = state.get('specs', {})
    results = []
    if specs.get('ram_capacity_gb', 0) < 16:
        results.append('RAM insufficient')
    return {**state, 'validation_results': results}

def security_scan(state: DesktopState) -> DesktopState:
    return {**state, 'status': 'Security Verified'}

builder = StateGraph(DesktopState)
builder.add_node('validate', validate_specs)
builder.add_node('security', security_scan)
builder.set_entry_point('validate')
builder.add_edge('validate', 'security')
builder.add_edge('security', END)
graph = builder.compile()
