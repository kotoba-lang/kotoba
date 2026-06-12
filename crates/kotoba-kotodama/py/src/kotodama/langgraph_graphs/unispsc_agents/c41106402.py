from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrimerState(TypedDict):
    primer_type: str
    purity_check: bool
    storage_validated: bool

def validate_purity(state: PrimerState):
    return {"purity_check": True}

def validate_storage(state: PrimerState):
    return {"storage_validated": True}

graph = StateGraph(PrimerState)
graph.add_node("purity", validate_purity)
graph.add_node("storage", validate_storage)
graph.set_entry_point("purity")
graph.add_edge("purity", "storage")
graph.add_edge("storage", END)
graph = graph.compile()
