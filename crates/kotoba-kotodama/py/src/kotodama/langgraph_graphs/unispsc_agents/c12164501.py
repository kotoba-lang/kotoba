from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_code: str
    purity_check: bool
    compliance_risk: List[str]
    process_steps: List[str]

def validate_purity(state: CatalystState):
    # Simulate purity check logic
    return {"purity_check": True, "process_steps": ["Purity validation passed"]}

def assess_risk(state: CatalystState):
    # Simulate regulatory compliance check
    return {"compliance_risk": ["dangerous-goods", "dual-use-export-control"], "process_steps": ["Risk assessment completed"]}

builder = StateGraph(CatalystState)
builder.add_node("validate_purity", validate_purity)
builder.add_node("assess_risk", assess_risk)
builder.add_edge("validate_purity", "assess_risk")
builder.set_entry_point("validate_purity")
builder.add_edge("assess_risk", END)

graph = builder.compile()
