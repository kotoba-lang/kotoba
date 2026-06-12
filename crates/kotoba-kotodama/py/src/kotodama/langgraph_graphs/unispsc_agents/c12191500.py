from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AdditiveState(TypedDict):
    batch_id: str
    purity_check: bool
    compliance_verified: bool
    approval_path: List[str]

def validate_purity(state: AdditiveState):
    return {"purity_check": True, "approval_path": ["PURITY_VALIDATED"]}

def check_compliance(state: AdditiveState):
    return {"compliance_verified": True, "approval_path": state["approval_path"] + ["COMPLIANCE_CLEARED"]}

graph = StateGraph(AdditiveState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
