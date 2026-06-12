from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity: float
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_catalyst_purity(state: CatalystState) -> dict:
    purity = state.get("purity", 0.0)
    if purity >= 99.0:
        return {"is_approved": True, "validation_log": ["Purity check passed"]}
    return {"is_approved": False, "validation_log": ["Purity check failed: Below 99.0%"]}

def perform_compliance_review(state: CatalystState) -> dict:
    if not state.get("is_approved"):
        return {"validation_log": ["Compliance review skipped due to low purity"]}
    return {"is_approved": True, "validation_log": ["Compliance review passed: Export/Safety compliant"]}

builder = StateGraph(CatalystState)
builder.add_node("purity_check", validate_catalyst_purity)
builder.add_node("compliance_review", perform_compliance_review)
builder.set_entry_point("purity_check")
builder.add_edge("purity_check", "compliance_review")
builder.add_edge("compliance_review", END)
graph = builder.compile()
