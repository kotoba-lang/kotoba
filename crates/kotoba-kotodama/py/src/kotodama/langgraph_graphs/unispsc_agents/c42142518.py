from typing import TypedDict
from langgraph.graph import StateGraph, END

class BiopsyState(TypedDict):
    device_id: str
    compliance_ok: bool
    sterilization_verified: bool

def validate_compliance(state: BiopsyState):
    # Simulate regulatory validation logic
    return {"compliance_ok": True}

def verify_sterility(state: BiopsyState):
    # Simulate sterility inspection logic
    return {"sterilization_verified": True}

graph = StateGraph(BiopsyState)
graph.add_node("validate", validate_compliance)
graph.add_node("sterility", verify_sterility)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterility")
graph.add_edge("sterility", END)
graph = graph.compile()
