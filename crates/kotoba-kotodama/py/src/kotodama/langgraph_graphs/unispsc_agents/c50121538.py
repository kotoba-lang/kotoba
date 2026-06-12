from typing import TypedDict
from langgraph.graph import StateGraph, END

class FishProcurementState(TypedDict):
    product_name: str
    quality_score: float
    haccp_compliant: bool
    approved: bool

def validate_certification(state: FishProcurementState) -> FishProcurementState:
    state['haccp_compliant'] = True
    return state

def approval_check(state: FishProcurementState) -> str:
    return 'approved' if state['haccp_compliant'] else 'rejected'

graph = StateGraph(FishProcurementState)
graph.add_node('ValidateCert', validate_certification)
graph.add_edge('ValidateCert', END)
graph.set_entry_point('ValidateCert')
graph = graph.compile()
