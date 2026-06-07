from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    batch_quality_check: bool
    is_expired: bool
    approved: bool

def validate_batch(state: ReagentState) -> ReagentState:
    # Logic to check batch certificate and expiration status
    state['batch_quality_check'] = True
    return state

def check_expiry(state: ReagentState) -> ReagentState:
    # Logic to compare current date vs expiration_date
    state['is_expired'] = False
    return state

def final_approval(state: ReagentState) -> ReagentState:
    if state['batch_quality_check'] and not state['is_expired']:
        state['approved'] = True
    return state

graph = StateGraph(ReagentState)
graph.add_node("validate", validate_batch)
graph.add_node("expiry", check_expiry)
graph.add_node("approve", final_approval)
graph.add_edge("validate", "expiry")
graph.add_edge("expiry", "approve")
graph.add_edge("approve", END)
graph.set_entry_point("validate")
graph = graph.compile()
