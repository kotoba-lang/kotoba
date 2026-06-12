from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SafetyState(TypedDict):
    equipment_type: str
    compliance_docs: List[str]
    is_approved: bool

def validate_certification(state: SafetyState):
    # Simulate regulatory compliance check for water rescue gear
    return {"is_approved": len(state.get("compliance_docs", [])) > 2}

def route_by_type(state: SafetyState):
    return "approve" if state["is_approved"] else "manual_review"

graph = StateGraph(SafetyState)
graph.add_node("validate", validate_certification)
graph.add_edge("validate", END)
graph.set_entry_point("validate")
graph = graph.compile()
