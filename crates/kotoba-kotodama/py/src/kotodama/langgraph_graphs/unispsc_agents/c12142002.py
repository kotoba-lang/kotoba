from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    commodity_code: str
    purity_check: bool
    safety_clearance: bool
    finalized: bool

def validate_purity(state: ChemicalState):
    # Simulate purity verification logic
    return {"purity_check": True}

def check_safety_protocols(state: ChemicalState):
    # Simulate dual-use/safety check
    return {"safety_clearance": True}

def finalize_procurement(state: ChemicalState):
    return {"finalized": True}

graph = StateGraph(ChemicalState)
graph.add_node("purity", validate_purity)
graph.add_node("safety", check_safety_protocols)
graph.add_node("finalize", finalize_procurement)
graph.add_edge("purity", "safety")
graph.add_edge("safety", "finalize")
graph.add_edge("finalize", END)
graph.set_entry_point("purity")
graph = graph.compile()
