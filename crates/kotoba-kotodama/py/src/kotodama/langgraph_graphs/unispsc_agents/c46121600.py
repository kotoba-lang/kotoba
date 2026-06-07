from typing import TypedDict
from langgraph.graph import StateGraph, END

class MissileProcurementState(TypedDict):
    export_license_verified: bool
    compliance_passed: bool
    technical_review: bool

def verify_compliance(state: MissileProcurementState):
    # Business logic for ITAR/EAR compliance check
    return {"compliance_passed": True}

def conduct_technical_review(state: MissileProcurementState):
    # Specialized subsystem diagnostic workflow
    return {"technical_review": True}

graph = StateGraph(MissileProcurementState)
graph.add_node("verify", verify_compliance)
graph.add_node("review", conduct_technical_review)
graph.set_entry_point("verify")
graph.add_edge("verify", "review")
graph.add_edge("review", END)
graph = graph.compile()
