from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SwineProcurementState(TypedDict):
    commodity_id: str
    health_status: bool
    quarantine_clearance: bool
    processing_steps: List[str]

def check_health_status(state: SwineProcurementState) -> SwineProcurementState:
    state['health_status'] = True
    return state

def verify_quarantine(state: SwineProcurementState) -> SwineProcurementState:
    state['quarantine_clearance'] = True
    return state

def route_to_processing(state: SwineProcurementState) -> str:
    if state['health_status'] and state['quarantine_clearance']:
        return 'process_shipment'
    return END

builder = StateGraph(SwineProcurementState)
builder.add_node('check_health', check_health_status)
builder.add_node('verify_quarantine', verify_quarantine)
builder.add_edge('check_health', 'verify_quarantine')
builder.add_conditional_edges('verify_quarantine', route_to_processing)
builder.set_entry_point('check_health')

graph = builder.compile()
