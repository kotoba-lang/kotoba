from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HypromelloseState(TypedDict):
    batch_id: str
    viscosity: float
    coa_verified: bool
    compliant: bool

def validate_coa(state: HypromelloseState):
    return {"coa_verified": state.get("viscosity", 0) > 0}

def check_compliance(state: HypromelloseState):
    return {"compliant": state["coa_verified"] and state["viscosity"] >= 5.0}

graph = StateGraph(HypromelloseState)
graph.add_node("validate_coa", validate_coa)
graph.add_node("check_compliance", check_compliance)
graph.set_entry_point("validate_coa")
graph.add_edge("validate_coa", "check_compliance")
graph.add_edge("check_compliance", END)
graph = graph.compile()
