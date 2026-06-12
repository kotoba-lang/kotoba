from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from operator import add

class GrainState(TypedDict):
    commodity_code: str
    quality_score: float
    quarantine_passed: bool
    final_status: str

def validate_quality(state: GrainState) -> GrainState:
    # Logic for checking moisture/GMO specs
    state['quality_score'] = 0.95
    return state

def check_quarantine(state: GrainState) -> GrainState:
    state['quarantine_passed'] = True
    return state

def finalize_procurement(state: GrainState) -> GrainState:
    state['final_status'] = 'READY_FOR_SHIPMENT'
    return state

graph = StateGraph(GrainState)
graph.add_node('validate_quality', validate_quality)
graph.add_node('check_quarantine', check_quarantine)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate_quality')
graph.add_edge('validate_quality', 'check_quarantine')
graph.add_edge('check_quarantine', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
