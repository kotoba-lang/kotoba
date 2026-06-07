from typing import TypedDict
from langgraph.graph import StateGraph, END

class TrainingState(TypedDict):
    content_id: str
    compliance_score: float
    requires_review: bool

def validate_content(state: TrainingState):
    # Simulate content validation logic for tolerance training materials
    score = 0.95 if 'bias_check' in state else 0.5
    return {"compliance_score": score, "requires_review": score < 0.8}

def route_by_compliance(state: TrainingState):
    return "review" if state["requires_review"] else "approve"

graph = StateGraph(TrainingState)
graph.add_node("validate", validate_content)
graph.add_edge("validate", END)
graph.set_entry_point("validate")
graph = graph.compile()
