from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class ChemicalIngestState(TypedDict):
    material_id: str
    purity_validated: bool
    safety_verified: bool

def validate_purity(state: ChemicalIngestState) -> ChemicalIngestState:
    # Logic to verify purity against specs
    return {"purity_validated": True}

def verify_safety(state: ChemicalIngestState) -> ChemicalIngestState:
    # Logic for safety protocols
    return {"safety_verified": True}

graph = StateGraph(ChemicalIngestState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("verify_safety", verify_safety)
graph.add_edge("validate_purity", "verify_safety")
graph.add_edge("verify_safety", END)
graph.set_entry_point("validate_purity")
graph = graph.compile()
