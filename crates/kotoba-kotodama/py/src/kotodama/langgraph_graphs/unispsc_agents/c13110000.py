from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class EnergyProcurementState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    compliance_status: bool
    messages: Annotated[list, add_messages]

def validate_energy_quality(state: EnergyProcurementState):
    # Simulate quality inspection for crude oil/fuels
    metrics = state.get('quality_metrics', {})
    is_safe = metrics.get('flash_point', 0) > 60
    return {'compliance_status': is_safe}

def update_compliance_records(state: EnergyProcurementState):
    return {'messages': ['Quality check passed. Compliance records updated.']}

builder = StateGraph(EnergyProcurementState)
builder.add_node('inspect', validate_energy_quality)
builder.add_node('compliance', update_compliance_records)
builder.add_edge('inspect', 'compliance')
builder.add_edge('compliance', END)
builder.set_entry_point('inspect')
graph = builder.compile()
