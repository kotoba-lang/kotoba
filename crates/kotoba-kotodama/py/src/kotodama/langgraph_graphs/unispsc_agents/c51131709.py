from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    purity_check: bool
    gmp_verified: bool
    approved: bool

def validate_purity(state: PharmState):
    return {"purity_check": True}

def verify_gmp(state: PharmState):
    return {"gmp_verified": True}

def final_decision(state: PharmState):
    return {"approved": state["purity_check"] and state["gmp_verified"]}

graph = StateGraph(PharmState)
graph.add_node("validate", validate_purity)
graph.add_node("verify", verify_gmp)
graph.add_node("decision", final_decision)
graph.set_entry_point("validate")
graph.add_edge("validate", "verify")
graph.add_edge("verify", "decision")
graph.add_edge("decision", END)
graph = graph.compile()
