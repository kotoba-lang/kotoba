from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class LivestockProcurementState(TypedDict):
    animal_id: str
    quarantine_status: str
    health_checks: list[str]
    approved: bool

def validate_livestock_health(state: LivestockProcurementState):
    # Simulate bio-security validation logic
    health_log = state.get('health_checks', [])
    status = 'APPROVED' if len(health_log) > 2 else 'PENDING'
    return {'quarantine_status': status, 'approved': status == 'APPROVED'}

def update_registry(state: LivestockProcurementState):
    # Simulate blockchain registry update
    return {'quarantine_status': 'REGISTERED'}

builder = StateGraph(LivestockProcurementState)
builder.add_node('validate', validate_livestock_health)
builder.add_node('registry', update_registry)
builder.add_edge('validate', 'registry')
builder.add_edge('registry', END)
builder.set_entry_point('validate')
graph = builder.compile()
