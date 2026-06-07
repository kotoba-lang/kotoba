from typing import TypedDict
from langgraph.graph import StateGraph, END

class WoundCareState(TypedDict):
    product_id: str
    is_sterile: bool
    compliance_passed: bool

def validate_sterility(state: WoundCareState):
    return {"is_sterile": True}

def check_compliance(state: WoundCareState):
    # Business logic for regulatory check
    return {"compliance_passed": True}

graph = StateGraph(WoundCareState)
graph.add_node("validate_sterility", validate_sterility)
graph.add_node("check_compliance", check_compliance)
graph.set_entry_point("validate_sterility")
graph.add_edge("validate_sterility", "check_compliance")
graph.add_edge("check_compliance", END)
graph = graph.compile()
