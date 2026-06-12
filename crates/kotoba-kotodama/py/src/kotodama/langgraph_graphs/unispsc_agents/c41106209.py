from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabSupplyState(TypedDict):
    purity_validated: bool
    temp_log_verified: bool
    approved: bool

def validate_purity(state: LabSupplyState):
    return {"purity_validated": True}

def verify_storage(state: LabSupplyState):
    return {"temp_log_verified": True}

def final_check(state: LabSupplyState):
    approved = state["purity_validated"] and state["temp_log_verified"]
    return {"approved": approved}

graph = StateGraph(LabSupplyState)
graph.add_node("validate", validate_purity)
graph.add_node("storage", verify_storage)
graph.add_node("approval", final_check)
graph.set_entry_point("validate")
graph.add_edge("validate", "storage")
graph.add_edge("storage", "approval")
graph.add_edge("approval", END)
graph.add_edge("approval", END)
graph = graph.compile()
