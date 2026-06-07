from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PulpProcessState(TypedDict):
    batch_id: str
    quality_metrics: dict
    approved: bool

def validate_pulp_spec(state: PulpProcessState) -> PulpProcessState:
    metrics = state.get("quality_metrics", {})
    # Ensure moisture < 12%
    state["approved"] = metrics.get("moisture", 100) < 12
    return state

def route_by_approval(state: PulpProcessState) -> str:
    return "end" if state.get("approved") else "reject"

graph = StateGraph(PulpProcessState)
graph.add_node("validate", validate_pulp_spec)
graph.add_node("reject", lambda s: s)
graph.set_entry_point("validate")
graph.add_conditional_edges("validate", route_by_approval, {"end": END, "reject": "reject"})
graph.add_edge("reject", END)
graph = graph.compile()
