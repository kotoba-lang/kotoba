from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugState(TypedDict):
    batch_id: str
    compliance_checked: bool
    is_approved: bool

def validate_compliance(state: DrugState):
    # Simulate GXP/Pharmacopoeia regulatory check
    return {"compliance_checked": True}

def approval_check(state: DrugState):
    return {"is_approved": state["compliance_checked"]}

graph = StateGraph(DrugState)
graph.add_node("validate", validate_compliance)
graph.add_node("approval", approval_check)
graph.set_entry_point("validate")
graph.add_edge("validate", "approval")
graph.add_edge("approval", END)
graph = graph.compile()
