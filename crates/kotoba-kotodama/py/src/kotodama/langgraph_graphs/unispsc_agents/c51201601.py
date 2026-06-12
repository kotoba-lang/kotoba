from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    biosafety_level: int
    temp_compliance: bool
    permits_verified: bool

def validate_biosafety(state: ProcurementState):
    return {"biosafety_level": state.get("biosafety_level", 3)}

def verify_permit(state: ProcurementState):
    return {"permits_verified": True}

workflow = StateGraph(ProcurementState)
workflow.add_node("validate_biosafety", validate_biosafety)
workflow.add_node("verify_permit", verify_permit)
workflow.set_entry_point("validate_biosafety")
workflow.add_edge("validate_biosafety", "verify_permit")
workflow.add_edge("verify_permit", END)
graph = workflow.compile()
