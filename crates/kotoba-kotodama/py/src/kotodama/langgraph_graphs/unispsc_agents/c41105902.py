from typing import TypedDict
from langgraph.graph import StateGraph, END

class cDNAState(TypedDict):
    library_id: str
    qc_passed: bool
    shipping_temp_verified: bool

def validate_library_specs(state: cDNAState):
    return {"qc_passed": True}

def check_cold_chain(state: cDNAState):
    return {"shipping_temp_verified": True}

graph = StateGraph(cDNAState)
graph.add_node("validate", validate_library_specs)
graph.add_node("cold_chain", check_cold_chain)
graph.set_entry_point("validate")
graph.add_edge("validate", "cold_chain")
graph.add_edge("cold_chain", END)
graph = graph.compile()
