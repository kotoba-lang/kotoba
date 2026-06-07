from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    item_name: str
    compliance_checked: bool
    sterility_verified: bool

def validate_compliance(state: DentalSupplyState):
    return {"compliance_checked": True}

def verify_sterility(state: DentalSupplyState):
    return {"sterility_verified": True}

graph = StateGraph(DentalSupplyState)
graph.add_node("validate", validate_compliance)
graph.add_node("verify", verify_sterility)
graph.set_entry_point("validate")
graph.add_edge("validate", "verify")
graph.add_edge("verify", END)
graph = graph.compile()
