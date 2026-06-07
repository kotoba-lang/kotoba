from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    gmp_verified: bool
    purity_level: float
    status: str

def check_gmp(state: PharmState):
    return {"gmp_verified": True if state.get("gmp_verified") else False}

def validate_purity(state: PharmState):
    purity = state.get("purity_level", 0)
    return {"status": "VALID" if purity >= 99.0 else "REJECTED"}

graph = StateGraph(PharmState)
graph.add_node("check_gmp", check_gmp)
graph.add_node("validate_purity", validate_purity)
graph.set_entry_point("check_gmp")
graph.add_edge("check_gmp", "validate_purity")
graph.add_edge("validate_purity", END)
graph = graph.compile()
