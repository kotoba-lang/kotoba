from typing import TypedDict
from langgraph.graph import StateGraph, END

class BookStorageState(TypedDict):
    spec_completed: bool
    safety_verified: bool
    procurement_status: str

def validate_specs(state: BookStorageState):
    return {"spec_completed": True}

def verify_safety(state: BookStorageState):
    return {"safety_verified": True, "procurement_status": "Ready for RFP"}

graph = StateGraph(BookStorageState)
graph.add_node("validate", validate_specs)
graph.add_node("verify", verify_safety)
graph.add_edge("validate", "verify")
graph.add_edge("verify", END)
graph.set_entry_point("validate")
graph = graph.compile()
