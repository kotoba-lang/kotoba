from typing import TypedDict
from langgraph.graph import StateGraph, END

class ScaleValidationState(TypedDict):
    capacity: float
    ip_rating: str
    is_calibrated: bool
    approved: bool

def validate_specs(state: ScaleValidationState):
    # Business logic for bench scale procurement validation
    if state.get('capacity', 0) > 0 and state.get('is_calibrated') is True:
        return {'approved': True}
    return {'approved': False}

def process_ip_rating(state: ScaleValidationState):
    ip = state.get('ip_rating', 'IP20')
    print(f'Processing IP protection check: {ip}')
    return {}

builder = StateGraph(ScaleValidationState)
builder.add_node('validate', validate_specs)
builder.add_node('ip_check', process_ip_rating)
builder.set_entry_point('validate')
builder.add_edge('validate', 'ip_check')
builder.add_edge('ip_check', END)
graph = builder.compile()
