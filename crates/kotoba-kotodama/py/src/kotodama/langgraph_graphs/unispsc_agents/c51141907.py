from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    gmp_status: bool
    purity_level: float
    approved: bool

def validate_gmp(state: ProcurementState):
    return {"gmp_status": state.get("gmp_status", False)}

def validate_purity(state: ProcurementState):
    purity = state.get("purity_level", 0.0)
    return {"approved": purity >= 99.5}

graph = StateGraph(ProcurementState)
graph.add_node("gmp_check", validate_gmp)
graph.add_node("purity_check", validate_purity)
graph.set_entry_point("gmp_check")
graph.add_edge("gmp_check", "purity_check")
graph.add_edge("purity_check", END)
graph = graph.compile()
