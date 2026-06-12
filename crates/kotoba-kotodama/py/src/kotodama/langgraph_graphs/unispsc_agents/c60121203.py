from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PaintState(TypedDict):
    material_name: str
    toxicity_tested: bool
    pigment_load: float
    status: str

def validate_safety(state: PaintState):
    return {"toxicity_tested": True, "status": "verified" if state.get("pigment_load", 0) > 0 else "error"}

def approve_procurement(state: PaintState):
    return {"status": "approved"}

graph = StateGraph(PaintState)
graph.add_node("validate", validate_safety)
graph.add_node("approve", approve_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
