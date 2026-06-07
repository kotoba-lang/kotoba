from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    purity_level: float
    gmp_certified: bool
    compliance_report: str

def validate_gmp(state: PharmState):
    return {"gmp_certified": state.get("gmp_certified", False)}

def check_purity(state: PharmState):
    is_pure = state.get("purity_level", 0) >= 99.9
    return {"compliance_report": "Approved" if is_pure else "Rejected"}

graph = StateGraph(PharmState)
graph.add_node("validate_gmp", validate_gmp)
graph.add_node("check_purity", check_purity)
graph.set_entry_point("validate_gmp")
graph.add_edge("validate_gmp", "check_purity")
graph.add_edge("check_purity", END)
graph = graph.compile()
