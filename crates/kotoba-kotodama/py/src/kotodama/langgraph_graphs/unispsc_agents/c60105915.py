from typing import TypedDict
from langgraph.graph import StateGraph, END

class TrainingState(TypedDict):
    content_id: str
    compliance_verified: bool
    approved: bool

def validate_compliance(state: TrainingState):
    # Simulate verification of regulatory standards
    return {"compliance_verified": True}

def approval_step(state: TrainingState):
    # Simulate procurement final review
    return {"approved": state["compliance_verified"]}

graph = StateGraph(TrainingState)
graph.add_node("validate", validate_compliance)
graph.add_node("approve", approval_step)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
