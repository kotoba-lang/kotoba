from typing import TypedDict
from langgraph.graph import StateGraph, END

class HeparinState(TypedDict):
    batch_id: str
    purity_check: bool
    temp_log_verified: bool
    gmp_status: bool

def validate_purity(state: HeparinState):
    return {"purity_check": True} if state.get("purity_percentage", 0) >= 99.0 else {"purity_check": False}

def verify_storage(state: HeparinState):
    return {"temp_log_verified": True}

graph = StateGraph(HeparinState)
graph.add_node("validate", validate_purity)
graph.add_node("storage", verify_storage)
graph.set_entry_point("validate")
graph.add_edge("validate", "storage")
graph.add_edge("storage", END)
graph = graph.compile()
