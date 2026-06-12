from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ReagentProcessState(TypedDict):
    reagent_id: str
    safety_check_passed: bool
    logistics_status: str
    risk_flags: List[str]

def validate_safety_compliance(state: ReagentProcessState):
    # Simulate rigid safety compliance check
    return {"safety_check_passed": True, "risk_flags": ["dangerous-goods"]}

def prepare_logistics(state: ReagentProcessState):
    return {"logistics_status": "Secure Transport Scheduled"}

builder = StateGraph(ReagentProcessState)
builder.add_node("safety_check", validate_safety_compliance)
builder.add_node("logistics", prepare_logistics)
builder.add_edge("safety_check", "logistics")
builder.add_edge("logistics", END)
builder.set_entry_point("safety_check")
graph = builder.compile()
