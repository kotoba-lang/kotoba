from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PulpIngestState(TypedDict):
    pulp_batch_id: str
    quality_metrics: dict
    approved: bool

def validate_pulp_quality(state: PulpIngestState):
    metrics = state.get("quality_metrics", {})
    is_valid = metrics.get("brightness", 0) > 80 and metrics.get("moisture", 10) < 12
    return {"approved": is_valid}

def route_pulp_batch(state: PulpIngestState):
    return "approved" if state.get("approved") else "rejected"

builder = StateGraph(PulpIngestState)
builder.add_node("validate", validate_pulp_quality)
builder.add_edge("validate", END)
builder.set_entry_point("validate")
graph = builder.compile()
