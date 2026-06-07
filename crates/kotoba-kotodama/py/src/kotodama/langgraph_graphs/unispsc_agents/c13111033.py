from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    sds_verified: bool
    safety_check_passed: bool
    log: Sequence[str]

def verify_sds(state: ProcurementState) -> dict:
    # Simulate SDS verification logic
    verified = True
    return {"sds_verified": verified, "log": ["SDS verified against global safety standards"]}

def safety_validation(state: ProcurementState) -> dict:
    # Simulate hazard class validation
    passed = state.get("sds_verified", False)
    return {"safety_check_passed": passed, "log": ["Safety validation check completed"]}

workflow = StateGraph(ProcurementState)
workflow.add_node("verify_sds", verify_sds)
workflow.add_node("safety_validation", safety_validation)
workflow.set_entry_point("verify_sds")
workflow.add_edge("verify_sds", "safety_validation")
workflow.add_edge("safety_validation", END)
graph = workflow.compile()
