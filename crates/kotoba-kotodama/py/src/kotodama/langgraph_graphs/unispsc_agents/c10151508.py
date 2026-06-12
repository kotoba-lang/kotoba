from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    quality_score: float
    inspection_passed: bool
    traceability_verified: bool

def validate_quality(state: ProcurementState) -> ProcurementState:
    state['quality_score'] = 95.0
    state['inspection_passed'] = True
    return state

def verify_traceability(state: ProcurementState) -> ProcurementState:
    state['traceability_verified'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('quality_check', validate_quality)
graph.add_node('traceability_check', verify_traceability)
graph.set_entry_point('quality_check')
graph.add_edge('quality_check', 'traceability_check')
graph.add_edge('traceability_check', END)
graph = graph.compile()
