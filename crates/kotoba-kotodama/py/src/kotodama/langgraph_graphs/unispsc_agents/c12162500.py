from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    logistics_status: str

def validate_purity(state: ChemicalState):
    # Simulate high-purity validation logic
    is_pure = True
    return {"purity_check": is_pure}

def check_safety(state: ChemicalState):
    # Simulate regulatory safety check
    return {"safety_clearance": True}

graph = StateGraph(ChemicalState)
graph.add_node("validate", validate_purity)
graph.add_node("safety", check_safety)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
