from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class FeedSupplyState(TypedDict):
    supply_id: str
    quality_score: float
    inspection_passed: bool

def validate_batch(state: FeedSupplyState) -> FeedSupplyState:
    # Specialized logic for corn livestock feed moisture/toxin inspection
    if state.get('quality_score', 0) > 0.8:
        return {**state, 'inspection_passed': True}
    return {**state, 'inspection_passed': False}

def route_by_quality(state: FeedSupplyState) -> str:
    return 'pass' if state['inspection_passed'] else 'fail'

builder = StateGraph(FeedSupplyState)
builder.add_node('validate', validate_batch)
builder.add_edge('validate', END)
builder.set_entry_point('validate')
graph = builder.compile()
