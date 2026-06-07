from typing import TypedDict
from langgraph.graph import StateGraph, END

class DNAQuantState(TypedDict):
    batch_id: str
    purity_check: bool
    storage_temp_verified: bool

def validate_purity(state: DNAQuantState):
    return {"purity_check": True}

def verify_cold_chain(state: DNAQuantState):
    return {"storage_temp_verified": True}

graph = StateGraph(DNAQuantState)
graph.add_node("validate", validate_purity)
graph.add_node("cold_chain", verify_cold_chain)
graph.add_edge("validate", "cold_chain")
graph.add_edge("cold_chain", END)
graph.set_entry_point("validate")
graph = graph.compile()
