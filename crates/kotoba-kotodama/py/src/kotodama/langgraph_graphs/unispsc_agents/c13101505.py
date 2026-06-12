from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AdditiveState(TypedDict):
    commodity_code: str
    sds_verified: bool
    flash_point: float
    compatibility_check: bool
    approval_status: str

def verify_sds(state: AdditiveState):
    # Simulate SDS validation logic
    return {"sds_verified": True}

def check_compatibility(state: AdditiveState):
    # Simulate chemical compatibility check
    return {"compatibility_check": state.get("flash_point", 0) > 60.0}

def finalize_approval(state: AdditiveState):
    if state["sds_verified"] and state["compatibility_check"]:
        return {"approval_status": "APPROVED"}
    return {"approval_status": "REJECTED"}

graph = StateGraph(AdditiveState)
graph.add_node("verify_sds", verify_sds)
graph.add_node("check_compatibility", check_compatibility)
graph.add_node("finalize", finalize_approval)
graph.add_edge("verify_sds", "check_compatibility")
graph.add_edge("check_compatibility", "finalize")
graph.add_edge("finalize", END)
graph.set_entry_point("verify_sds")
graph = graph.compile()
