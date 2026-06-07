from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class DocState(TypedDict):
    doc_id: str
    compliance_status: str
    risk_score: int

def validate_metadata(state: DocState):
    # Simulate validation logic for document compliance
    return {"compliance_status": "VALIDATED" if state.get("doc_id") else "FAILED"}

def perform_audit(state: DocState):
    # Simulate audit trail check
    return {"risk_score": 1 if state["compliance_status"] == "VALIDATED" else 10}

builder = StateGraph(DocState)
builder.add_node("validate", validate_metadata)
builder.add_node("audit", perform_audit)
builder.set_entry_point("validate")
builder.add_edge("validate", "audit")
builder.add_edge("audit", END)
graph = builder.compile()
