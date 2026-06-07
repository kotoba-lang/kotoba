from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AdhesiveState(TypedDict):
    product_id: str
    sds_verified: bool
    compliance_tags: List[str]
    approved: bool

def validate_sds(state: AdhesiveState):
    # Simulate chemical safety compliance check
    return {"sds_verified": True}

def check_compliance(state: AdhesiveState):
    # Simulate regulatory lookup
    return {"compliance_tags": ["VOC-compliant"], "approved": True}

graph = StateGraph(AdhesiveState)
graph.add_node("validate_sds", validate_sds)
graph.add_node("check_compliance", check_compliance)
graph.add_edge("validate_sds", "check_compliance")
graph.add_edge("check_compliance", END)
graph.set_entry_point("validate_sds")
graph = graph.compile()
