from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ReagentState(TypedDict):
    reagent_id: str
    quality_docs: Sequence[str]
    validation_status: str
    compliant: bool

def validate_purity(state: ReagentState):
    # Simulate CAD/Spec validation for purity
    return {"validation_status": "purity_verified", "compliant": True}

def check_regulations(state: ReagentState):
    # Simulate regulatory compliance check
    return {"validation_status": "regulation_cleared"}

builder = StateGraph(ReagentState)
builder.add_node("purity_check", validate_purity)
builder.add_node("regulatory_check", check_regulations)
builder.add_edge("purity_check", "regulatory_check")
builder.add_edge("regulatory_check", END)
builder.set_entry_point("purity_check")
graph = builder.compile()
